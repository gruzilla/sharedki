from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import secrets
import sqlite3
from threading import Lock

from dotenv import load_dotenv
from cryptography.fernet import Fernet, InvalidToken
from flask import Flask, jsonify, render_template, request, session
from flask_socketio import SocketIO, emit, join_room
from openai import OpenAI
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET")
socketio = SocketIO(app)
SERVER_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
API_KEY_ENCRYPTION_KEY = os.environ.get("API_KEY_ENCRYPTION_KEY", "").strip()
serverOpenAIClient = OpenAI(api_key=SERVER_OPENAI_API_KEY) if SERVER_OPENAI_API_KEY else None
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(app.root_path, "data", "cyberquest.db"))
SAVEGAMES_PATH = os.environ.get("SAVEGAMES_PATH", os.path.join(app.root_path, "savegames"))
VALID_AI_MODES = {"conversation", "independend"}
DEVICE_ID_WORDS = {
    "adjectives": (
        "brave", "bright", "calm", "clever", "eager", "fair", "gentle", "happy",
        "helpful", "honest", "humble", "jolly", "kind", "lively", "lucky", "merry",
        "mighty", "noble", "patient", "proud", "quick", "quiet", "steady", "witty"
    ),
    "colors": (
        "amber", "aqua", "azure", "beige", "black", "blue", "bronze", "coral",
        "crimson", "cyan", "golden", "green", "indigo", "ivory", "jade", "lilac",
        "lime", "magenta", "navy", "orange", "pink", "purple", "silver", "teal"
    ),
    "animals": (
        "badger", "beaver", "bison", "cat", "cobra", "dolphin", "eagle", "falcon",
        "fox", "gecko", "heron", "koala", "lemur", "lion", "otter", "owl",
        "panda", "parrot", "penguin", "rabbit", "raccoon", "tiger", "turtle", "wolf"
    ),
    "occupations": (
        "baker", "bike mechanic", "bus driver", "carpenter", "chef", "coach",
        "dentist", "doctor", "electrician", "engineer", "farmer", "firefighter",
        "gardener", "librarian", "musician", "nurse", "painter", "photographer",
        "pilot", "plumber", "scientist", "teacher", "taxi driver", "train conductor"
    )
}

def generate_device_identity():
    words = [secrets.choice(DEVICE_ID_WORDS[group])
             for group in ("adjectives", "colors", "animals", "occupations")]
    device_id = " ".join(words)
    device_code = "".join(word[0] for word in words)
    return device_id, device_code

def now():
    return datetime.now(timezone.utc).isoformat()

def create_game_state():
    return {
        "currentQuestion": 0, "currentAnswers": [], "storedAnswers": {},
        "questions": ["Wie lautet der Name eurer Gruppe?", "Wo seid ihr gerade?"],
        "gamePhase": "collecting", "aiMode": "conversation", "gptModel": "gpt-5.6-terra",
        "lastAiAnswerTokens": 0, "totalAiAnswerTokens": 0,
        "systemPrompt": "Du bist ein typischer österreichischer Teenager. Antworte immer auf Hochdeutsch. Verwende ab und an Apokopen und Kontraktionen. Du vertrittst eine Gruppe von Teenagern. Fasse dich kurz, wie in einer Fernsehquizshow – keine unnötigen Formulierungen oder Einleitungen. Wiederhole keine Teile der Frage in deiner Antwort. Zitiere in deinen Antwort nicht aus der Frage."
    }

def normalize_name(value):
    return "-".join(value.strip().lower().split()) if isinstance(value, str) else ""

def db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

def init_db():
    with db() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS game_sessions (
            session_name TEXT PRIMARY KEY, pin_hash TEXT NOT NULL, state_json TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT);
        CREATE TABLE IF NOT EXISTS participants (
            session_name TEXT NOT NULL, device_id TEXT NOT NULL, device_code TEXT,
            joined_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, PRIMARY KEY(session_name, device_id),
            FOREIGN KEY(session_name) REFERENCES game_sessions(session_name) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_name TEXT NOT NULL,
            question_index INTEGER NOT NULL, answer_text TEXT NOT NULL, source TEXT NOT NULL,
            participant_id TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY(session_name) REFERENCES game_sessions(session_name) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS game_session_api_keys (
            session_name TEXT PRIMARY KEY, encrypted_api_key TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(session_name) REFERENCES game_sessions(session_name) ON DELETE CASCADE);
        """)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(participants)")}
        if "device_code" not in columns:
            connection.execute("ALTER TABLE participants ADD COLUMN device_code TEXT")
init_db()

def record_for(name):
    with db() as connection:
        return connection.execute("SELECT * FROM game_sessions WHERE session_name = ?", (name,)).fetchone()

def state_for(record):
    state = json.loads(record["state_json"])
    state.setdefault("lastAiAnswerTokens", 0)
    state.setdefault("totalAiAnswerTokens", 0)
    connected_by_id = {
        client["device"]: client["deviceCode"]
        for client in globals().get("clients", {}).values()
        if client["session"] == record["session_name"] and client["role"] == "participant"
    }
    connected_devices = [
        {"id": device, "code": code}
        for device, code in sorted(connected_by_id.items())
    ]
    with db() as connection:
        answer_rows = connection.execute(
            """SELECT answers.answer_text, answers.source, participants.device_code
               FROM answers
               LEFT JOIN participants
                 ON participants.session_name=answers.session_name
                AND participants.device_id=answers.participant_id
               WHERE answers.session_name=? AND answers.question_index=?
               ORDER BY answers.id""",
            (record["session_name"], state["currentQuestion"])
        ).fetchall()
    current_answer_details = [
        {
            "answer": row["answer_text"],
            "deviceCode": row["device_code"] if row["source"] == "participant" else "AI"
        }
        for row in answer_rows
    ]
    state.update(sessionStatus=record["status"], startedAt=record["started_at"], endedAt=record["ended_at"],
                 connectedDevices=connected_devices, currentAnswerDetails=current_answer_details)
    return state

def save_state(name, state):
    clean = {k: v for k, v in state.items()
             if k not in {"sessionStatus", "startedAt", "endedAt", "connectedDevices", "currentAnswerDetails"}}
    with db() as connection:
        connection.execute("UPDATE game_sessions SET state_json = ? WHERE session_name = ?",
                           (json.dumps(clean, ensure_ascii=False), name))

def teacher_names():
    return session.setdefault("teacher_sessions", [])

def authorize(name):
    names = teacher_names()
    if name not in names:
        names.append(name)
        session["teacher_sessions"] = names
        session.modified = True

def requested_session(teacher=False):
    name = normalize_name(request.args.get("session"))
    if not name:
        return None, None, (jsonify(success=False, error="Session ID is required"), 400)
    record = record_for(name)
    if record is None:
        return name, None, (jsonify(success=False, error="Session not found"), 404)
    if teacher and name not in teacher_names():
        return name, record, (jsonify(success=False, error="Teacher login required"), 403)
    return name, record, None

def room(name):
    return "game:" + name

def broadcast(name):
    record = record_for(name)
    if record:
        socketio.emit("state_update", state_for(record), room=room(name))

ai_cache = {}
conversations = {}
request_locks = {}

class ApiKeyConfigurationError(Exception):
    pass

def api_key_cipher():
    if not API_KEY_ENCRYPTION_KEY:
        raise ApiKeyConfigurationError(
            "Personal API key storage is unavailable because API_KEY_ENCRYPTION_KEY is not configured"
        )
    try:
        return Fernet(API_KEY_ENCRYPTION_KEY.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exception:
        raise ApiKeyConfigurationError("API_KEY_ENCRYPTION_KEY is invalid") from exception

def stored_api_key_row(name):
    with db() as connection:
        return connection.execute(
            "SELECT encrypted_api_key FROM game_session_api_keys WHERE session_name=?",
            (name,)
        ).fetchone()

def decrypt_api_key(row):
    try:
        return api_key_cipher().decrypt(row["encrypted_api_key"].encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as exception:
        raise ApiKeyConfigurationError(
            "The stored personal API key cannot be decrypted with the configured encryption key"
        ) from exception

def credential_for(name):
    row = stored_api_key_row(name)
    if row is not None:
        api_key = decrypt_api_key(row)
        return OpenAI(api_key=api_key), "personal", hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    if serverOpenAIClient is not None:
        return serverOpenAIClient, "server", hashlib.sha256(SERVER_OPENAI_API_KEY.encode("utf-8")).hexdigest()
    raise ApiKeyConfigurationError("No OpenAI API key is configured")

def api_key_status_for(name):
    row = stored_api_key_row(name)
    configured = row is not None
    storage_error = None
    try:
        api_key_cipher()
        encryption_available = True
    except ApiKeyConfigurationError as exception:
        encryption_available = False
        storage_error = str(exception)
    status = {
        "personalKeyConfigured": configured,
        "encryptionAvailable": encryption_available,
        "serverKeyConfigured": bool(SERVER_OPENAI_API_KEY),
        "source": "personal" if configured else ("server" if SERVER_OPENAI_API_KEY else "none"),
        "usable": bool(configured or SERVER_OPENAI_API_KEY),
    }
    if storage_error:
        status["storageError"] = storage_error
    if configured:
        try:
            decrypt_api_key(row)
        except ApiKeyConfigurationError as exception:
            status["usable"] = False
            status["error"] = str(exception)
    return status

def test_openai_key(api_key, state):
    client = OpenAI(api_key=api_key)
    client.responses.create(
        model=state["gptModel"],
        input="Reply with OK.",
        max_output_tokens=16,
    )

def conversation_id(name, state, client, credential_id):
    signature = (state["gptModel"], state["systemPrompt"], credential_id)
    existing = conversations.get(name)
    if existing and existing["signature"] == signature:
        return existing["id"]
    conversation = client.conversations.create(
        metadata={"game_session": name[:512]},
        items=[{"type": "message", "role": "system", "content": state["systemPrompt"]}])
    conversations[name] = {"id": conversation.id, "signature": signature}
    return conversation.id

def ai_answer(name, state, question):
    client, _, credential_id = credential_for(name)
    if state["aiMode"] == "conversation":
        response = client.responses.create(
            model=state["gptModel"], conversation=conversation_id(name, state, client, credential_id),
            input=[{"role": "user", "content": question}], max_output_tokens=150)
        return response.output_text.strip(), response.usage.total_tokens
    key = (credential_id, state["gptModel"], state["systemPrompt"], question)
    if key in ai_cache:
        return ai_cache[key], 0
    response = client.chat.completions.create(
        model=state["gptModel"],
        messages=[{"role": "system", "content": state["systemPrompt"]},
                  {"role": "user", "content": question}],
        max_completion_tokens=150)
    answer = response.choices[0].message.content.strip()
    ai_cache[key] = answer
    return answer, response.usage.total_tokens

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/presenter")
def presenter():
    return render_template("presenter.html")

@app.route("/participant")
def participant():
    return render_template("participant.html")

@app.post("/participant/join")
def join_participant():
    name, record, error = requested_session()
    if error:
        return error
    if record["status"] != "live":
        return jsonify(success=False, error="This session is not live"), 409

    participant_devices = session.setdefault("participant_devices", {})
    assignment = participant_devices.get(name)
    if not isinstance(assignment, dict) or not assignment.get("id") or not assignment.get("code"):
        with db() as connection:
            existing_rows = connection.execute(
                "SELECT device_id, device_code FROM participants WHERE session_name=?",
                (name,)
            ).fetchall()
            existing_devices = {row["device_id"] for row in existing_rows}
            existing_codes = {row["device_code"] for row in existing_rows if row["device_code"]}

            device, base_code = generate_device_identity()
            while device in existing_devices:
                device, base_code = generate_device_identity()
            code = base_code
            suffix = 2
            while code in existing_codes:
                code = f"{base_code}{suffix}"
                suffix += 1

            timestamp = now()
            connection.execute(
                """INSERT INTO participants(session_name,device_id,device_code,joined_at,last_seen_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(session_name,device_id) DO UPDATE SET
                       device_code=excluded.device_code,
                       last_seen_at=excluded.last_seen_at""",
                (name, device, code, timestamp, timestamp)
            )
        assignment = {"id": device, "code": code}
        participant_devices[name] = assignment
        session["participant_devices"] = participant_devices
        session.modified = True
    return jsonify(success=True, deviceId=assignment["id"], deviceCode=assignment["code"])

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.post("/admin/create_session")
def create_session():
    data = request.get_json() or {}
    name, pin = normalize_name(data.get("session")), str(data.get("pin", ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,39}", name):
        return jsonify(success=False, error="Use 3–40 letters, numbers, hyphens, or underscores"), 400
    if len(pin) < 6:
        return jsonify(success=False, error="The teacher PIN must contain at least 6 characters"), 400
    try:
        with db() as connection:
            connection.execute("INSERT INTO game_sessions VALUES (?, ?, ?, 'prepared', ?, NULL, NULL)",
                               (name, generate_password_hash(pin), json.dumps(create_game_state()), now()))
    except sqlite3.IntegrityError:
        return jsonify(success=False, error="That session ID already exists"), 409
    authorize(name)
    return jsonify(success=True, session=name)

@app.post("/admin/login")
def login():
    data = request.get_json() or {}
    name = normalize_name(data.get("session"))
    record = record_for(name)
    if record is None or not check_password_hash(record["pin_hash"], str(data.get("pin", ""))):
        return jsonify(success=False, error="Unknown session ID or incorrect PIN"), 403
    authorize(name)
    return jsonify(success=True, session=name)

@app.post("/admin/logout")
def logout():
    name, _, error = requested_session(True)
    if error:
        return error
    names = teacher_names()
    names.remove(name)
    session["teacher_sessions"] = names
    session.modified = True
    return jsonify(success=True)

@app.get("/admin/get_state")
def get_state():
    _, record, error = requested_session(True)
    return error if error else jsonify(state_for(record))

@app.get("/admin/api_key_status")
def api_key_status():
    name, _, error = requested_session(True)
    return error if error else jsonify(api_key_status_for(name))

@app.post("/admin/api_key/test")
def test_api_key():
    _, record, error = requested_session(True)
    if error:
        return error
    api_key = str((request.get_json() or {}).get("apiKey", "")).strip()
    if not api_key:
        return jsonify(success=False, error="Enter an OpenAI API key"), 400
    if len(api_key) > 4096:
        return jsonify(success=False, error="The OpenAI API key is too long"), 400
    try:
        test_openai_key(api_key, state_for(record))
    except Exception as exception:
        return jsonify(success=False, error=f"OpenAI rejected the API key: {exception}"), 400
    return jsonify(success=True)

@app.post("/admin/api_key")
def save_api_key():
    name, record, error = requested_session(True)
    if error:
        return error
    api_key = str((request.get_json() or {}).get("apiKey", "")).strip()
    if not api_key:
        return jsonify(success=False, error="Enter an OpenAI API key"), 400
    if len(api_key) > 4096:
        return jsonify(success=False, error="The OpenAI API key is too long"), 400
    try:
        cipher = api_key_cipher()
        test_openai_key(api_key, state_for(record))
        encrypted = cipher.encrypt(api_key.encode("utf-8")).decode("ascii")
    except ApiKeyConfigurationError as exception:
        return jsonify(success=False, error=str(exception)), 503
    except Exception as exception:
        return jsonify(success=False, error=f"OpenAI rejected the API key: {exception}"), 400
    timestamp = now()
    with db() as connection:
        connection.execute(
            """INSERT INTO game_session_api_keys(session_name,encrypted_api_key,created_at,updated_at)
               VALUES(?,?,?,?)
               ON CONFLICT(session_name) DO UPDATE SET
                   encrypted_api_key=excluded.encrypted_api_key,
                   updated_at=excluded.updated_at""",
            (name, encrypted, timestamp, timestamp)
        )
    conversations.pop(name, None)
    return jsonify(success=True, status=api_key_status_for(name))

@app.delete("/admin/api_key")
def remove_api_key():
    name, _, error = requested_session(True)
    if error:
        return error
    with db() as connection:
        connection.execute("DELETE FROM game_session_api_keys WHERE session_name=?", (name,))
    conversations.pop(name, None)
    return jsonify(success=True, status=api_key_status_for(name))

@app.post("/admin/update_state")
def update_state():
    name, record, error = requested_session(True)
    if error:
        return error
    state, data = state_for(record), request.get_json() or {}
    if data.get("aiMode", state["aiMode"]) not in VALID_AI_MODES:
        return jsonify(success=False, error="Invalid AI mode"), 400
    old_index = state["currentQuestion"]
    for key, value in data.items():
        if key in {"sessionStatus", "startedAt", "endedAt", "connectedDevices", "currentAnswerDetails"}:
            continue
        if key == "currentQuestion" and value != old_index:
            state["storedAnswers"][str(old_index)] = list(state["currentAnswers"])
            state["currentAnswers"] = list(state["storedAnswers"].get(str(value), []))
        state[key] = value
    save_state(name, state)
    broadcast(name)
    return jsonify(success=True)

@app.post("/admin/start")
def start():
    name, record, error = requested_session(True)
    if error:
        return error
    state = state_for(record)
    state.update(currentQuestion=0, currentAnswers=[], storedAnswers={}, gamePhase="collecting",
                 lastAiAnswerTokens=0, totalAiAnswerTokens=0)
    clean = {
        key: value for key, value in state.items()
        if key not in {"sessionStatus", "startedAt", "endedAt", "connectedDevices", "currentAnswerDetails"}
    }
    active_participants = {
        (client["device"], client["deviceCode"])
        for client in clients.values()
        if client["session"] == name and client["role"] == "participant"
    }
    timestamp = now()
    with db() as connection:
        connection.execute("DELETE FROM participants WHERE session_name = ?", (name,))
        connection.execute("DELETE FROM answers WHERE session_name = ?", (name,))
        connection.executemany(
            """INSERT INTO participants(session_name,device_id,device_code,joined_at,last_seen_at)
               VALUES(?,?,?,?,?)""",
            [(name, device, code, timestamp, timestamp) for device, code in active_participants]
        )
        connection.execute("UPDATE game_sessions SET state_json=?, status='live', started_at=?, ended_at=NULL WHERE session_name=?",
                           (json.dumps(clean), timestamp, name))
    conversations.pop(name, None)
    broadcast(name)
    return jsonify(success=True)

@app.post("/admin/end")
def end():
    name, record, error = requested_session(True)
    if error:
        return error
    if record["status"] != "live":
        return jsonify(success=False, error="Only a live game can be ended"), 409
    with db() as connection:
        connection.execute("UPDATE game_sessions SET status='finished', ended_at=? WHERE session_name=?", (now(), name))
    broadcast(name)
    return jsonify(success=True, reportUrl="/admin/report?session=" + name)

@app.post("/admin/delete_answer")
def delete_answer():
    name, record, error = requested_session(True)
    if error:
        return error
    target = normalized(str((request.get_json() or {}).get("answer", "")))
    if not target:
        return jsonify(success=False, error="Answer is required"), 400

    state = state_for(record)
    index = state["currentQuestion"]
    remaining = [answer for answer in state["currentAnswers"] if normalized(str(answer)) != target]
    removed_from_state = len(state["currentAnswers"]) - len(remaining)
    state["currentAnswers"] = remaining
    state["storedAnswers"][str(index)] = list(remaining)
    save_state(name, state)

    with db() as connection:
        rows = connection.execute(
            "SELECT id, answer_text FROM answers WHERE session_name=? AND question_index=?",
            (name, index)
        ).fetchall()
        matching_ids = [(row["id"],) for row in rows if normalized(row["answer_text"]) == target]
        connection.executemany("DELETE FROM answers WHERE id=?", matching_ids)

    broadcast(name)
    return jsonify(success=True, removed=max(removed_from_state, len(matching_ids)))

@app.post("/admin/get_ai_answer")
def get_ai():
    name, record, error = requested_session(True)
    if error:
        return error
    if record["status"] != "live":
        return jsonify(success=False, error="Start the game before requesting AI answers"), 409
    state = state_for(record)
    index = state["currentQuestion"]
    if not 0 <= index < len(state["questions"]):
        return jsonify(success=False, error="Invalid question index"), 400
    lock = request_locks.setdefault(name, Lock())
    with lock:
        try:
            answer, tokens_used = ai_answer(name, state, state["questions"][index])
        except Exception as exception:
            return jsonify(success=False, error=str(exception)), 500
        state["currentAnswers"].append(answer)
        state["lastAiAnswerTokens"] = tokens_used
        state["totalAiAnswerTokens"] += tokens_used
        save_state(name, state)
        with db() as connection:
            connection.execute("INSERT INTO answers(session_name,question_index,answer_text,source,created_at) VALUES(?,?,?,'ai',?)",
                               (name, index, answer, now()))
    broadcast(name)
    return jsonify(success=True, answer=answer)

def normalized(value):
    return " ".join(re.findall(r"\w+", value.casefold(), re.UNICODE))

def save_game_snapshot(name, state):
    os.makedirs(SAVEGAMES_PATH, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = os.path.join(SAVEGAMES_PATH, f"{name}-{timestamp}.json")
    temporary = destination + ".tmp"
    with open(temporary, "w", encoding="utf-8") as snapshot:
        json.dump(state, snapshot, ensure_ascii=False, indent=2)
        snapshot.write("\n")
    os.replace(temporary, destination)

@app.get("/admin/report")
def report():
    name, record, error = requested_session(True)
    if error:
        return error
    state = state_for(record)
    save_game_snapshot(name, state)
    with db() as connection:
        rows = connection.execute("SELECT question_index,answer_text,source FROM answers WHERE session_name=? ORDER BY id", (name,)).fetchall()
        count = connection.execute("SELECT COUNT(*) FROM participants WHERE session_name=?", (name,)).fetchone()[0]
    questions = []
    for index, question in enumerate(state["questions"]):
        relevant = [row for row in rows if row["question_index"] == index]
        counts = Counter(normalized(row["answer_text"]) for row in relevant)
        duplicates = []
        for key, amount in counts.items():
            if key and amount > 1:
                duplicates.append({"answer": next(row["answer_text"] for row in relevant if normalized(row["answer_text"]) == key), "count": amount})
        questions.append({"question": question, "answers": relevant,
                          "aiAnswers": [row["answer_text"] for row in relevant if row["source"] == "ai"],
                          "duplicates": duplicates})
    duration = None
    if record["started_at"] and record["ended_at"]:
        duration = int((datetime.fromisoformat(record["ended_at"]) - datetime.fromisoformat(record["started_at"])).total_seconds())
    return render_template("report.html", session_name=name, record=record, questions=questions,
                           participant_count=count, duration_seconds=duration)

clients = {}

@socketio.on("connect")
def connected(auth):
    auth = auth or {}
    name, role = normalize_name(auth.get("session")), auth.get("role", "participant")
    record = record_for(name)
    if record is None:
        return False
    device = ""
    if role == "teacher":
        if name not in teacher_names():
            return False
    elif role == "participant":
        if record["status"] != "live":
            return False
        assignment = session.get("participant_devices", {}).get(name, {})
        if not isinstance(assignment, dict) or not assignment.get("id") or not assignment.get("code"):
            return False
        device, device_code = assignment["id"], assignment["code"]
        timestamp = now()
        with db() as connection:
            connection.execute(
                """INSERT INTO participants(session_name,device_id,device_code,joined_at,last_seen_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(session_name,device_id) DO UPDATE SET
                       device_code=excluded.device_code,
                       last_seen_at=excluded.last_seen_at""",
                (name, device, device_code, timestamp, timestamp)
            )
    elif role != "presenter":
        return False
    clients[request.sid] = {
        "session": name,
        "role": role,
        "device": device,
        "deviceCode": device_code if role == "participant" else ""
    }
    join_room(room(name))
    broadcast(name)

@socketio.on("disconnect")
def disconnected():
    client = clients.pop(request.sid, None)
    if client and client["role"] == "participant":
        broadcast(client["session"])

@socketio.on("participant_action")
def participant_action(data):
    client = clients.get(request.sid)
    if not client or client["role"] != "participant":
        return
    name, record = client["session"], record_for(client["session"])
    if not record or record["status"] != "live":
        return
    state, action = state_for(record), (data or {}).get("action")
    changed = False
    if action == "suggest_question" and state["gamePhase"] == "collecting":
        value = str(data.get("question", "")).strip()[:500]
        if value and value not in state["questions"]:
            state["questions"].append(value)
            changed = True
    elif action == "update_question" and state["gamePhase"] == "collecting":
        old, new = str(data.get("oldQuestion", "")).strip(), str(data.get("newQuestion", "")).strip()[:500]
        if old in state["questions"] and new:
            state["questions"][state["questions"].index(old)] = new
            changed = True
    elif action == "submit_answer" and state["gamePhase"] == "answering":
        value = str(data.get("answer", "")).strip()[:2000]
        if value:
            state["currentAnswers"].append(value)
            with db() as connection:
                connection.execute("""INSERT INTO answers(session_name,question_index,answer_text,source,participant_id,created_at)
                    VALUES(?,?,?,'participant',?,?)""",
                                   (name, state["currentQuestion"], value, client["device"], now()))
            changed = True
    if changed:
        save_state(name, state)
        broadcast(name)

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0")
