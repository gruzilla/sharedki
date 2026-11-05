from collections import Counter
from datetime import datetime, timezone
import json
import os
import re
import sqlite3
from threading import Lock

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from flask_socketio import SocketIO, emit, join_room
from openai import OpenAI
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET")
socketio = SocketIO(app)
openAIClient = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(app.root_path, "data", "cyberquest.db"))
SAVEGAMES_PATH = os.environ.get("SAVEGAMES_PATH", os.path.join(app.root_path, "savegames"))
VALID_AI_MODES = {"conversation", "independend"}

def now():
    return datetime.now(timezone.utc).isoformat()

def create_game_state():
    return {
        "currentQuestion": 0, "currentAnswers": [], "storedAnswers": {},
        "questions": ["Wie lautet der Name eurer Gruppe?", "Wo seid ihr gerade?"],
        "gamePhase": "collecting", "aiMode": "conversation", "gptModel": "gpt-5.6-terra",
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
            session_name TEXT NOT NULL, device_id TEXT NOT NULL, joined_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL, PRIMARY KEY(session_name, device_id),
            FOREIGN KEY(session_name) REFERENCES game_sessions(session_name) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_name TEXT NOT NULL,
            question_index INTEGER NOT NULL, answer_text TEXT NOT NULL, source TEXT NOT NULL,
            participant_id TEXT, created_at TEXT NOT NULL,
            FOREIGN KEY(session_name) REFERENCES game_sessions(session_name) ON DELETE CASCADE);
        """)
init_db()

def record_for(name):
    with db() as connection:
        return connection.execute("SELECT * FROM game_sessions WHERE session_name = ?", (name,)).fetchone()

def state_for(record):
    state = json.loads(record["state_json"])
    state.update(sessionStatus=record["status"], startedAt=record["started_at"], endedAt=record["ended_at"])
    return state

def save_state(name, state):
    clean = {k: v for k, v in state.items() if k not in {"sessionStatus", "startedAt", "endedAt"}}
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

def conversation_id(name, state):
    signature = (state["gptModel"], state["systemPrompt"])
    existing = conversations.get(name)
    if existing and existing["signature"] == signature:
        return existing["id"]
    conversation = openAIClient.conversations.create(
        metadata={"game_session": name[:512]},
        items=[{"type": "message", "role": "system", "content": state["systemPrompt"]}])
    conversations[name] = {"id": conversation.id, "signature": signature}
    return conversation.id

def ai_answer(name, state, question):
    if state["aiMode"] == "conversation":
        response = openAIClient.responses.create(
            model=state["gptModel"], conversation=conversation_id(name, state),
            input=[{"role": "user", "content": question}], max_output_tokens=150)
        return response.output_text.strip()
    key = (state["gptModel"], state["systemPrompt"], question)
    if key not in ai_cache:
        response = openAIClient.chat.completions.create(
            model=state["gptModel"],
            messages=[{"role": "system", "content": state["systemPrompt"]},
                      {"role": "user", "content": question}],
            max_completion_tokens=150)
        ai_cache[key] = response.choices[0].message.content.strip()
    return ai_cache[key]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/presenter")
def presenter():
    return render_template("presenter.html")

@app.route("/participant")
def participant():
    return render_template("participant.html")

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

@app.get("/admin/get_state")
def get_state():
    _, record, error = requested_session(True)
    return error if error else jsonify(state_for(record))

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
        if key in {"sessionStatus", "startedAt", "endedAt"}:
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
    state.update(currentQuestion=0, currentAnswers=[], storedAnswers={}, gamePhase="collecting")
    clean = {k: v for k, v in state.items() if k not in {"sessionStatus", "startedAt", "endedAt"}}
    with db() as connection:
        connection.execute("DELETE FROM participants WHERE session_name = ?", (name,))
        connection.execute("DELETE FROM answers WHERE session_name = ?", (name,))
        connection.execute("UPDATE game_sessions SET state_json=?, status='live', started_at=?, ended_at=NULL WHERE session_name=?",
                           (json.dumps(clean), now(), name))
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

@app.post("/admin/clear_answers")
def clear_answers():
    name, record, error = requested_session(True)
    if error:
        return error
    state = state_for(record)
    index = state["currentQuestion"]
    state["currentAnswers"] = []
    state["storedAnswers"][str(index)] = []
    save_state(name, state)
    with db() as connection:
        connection.execute("DELETE FROM answers WHERE session_name=? AND question_index=?", (name, index))
    broadcast(name)
    return jsonify(success=True)

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
            answer = ai_answer(name, state, state["questions"][index])
        except Exception as exception:
            return jsonify(success=False, error=str(exception)), 500
        state["currentAnswers"].append(answer)
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
    if role == "teacher":
        if name not in teacher_names():
            return False
    elif record["status"] != "live":
        return False
    device = str(auth.get("deviceId", ""))[:100]
    if role == "participant":
        if not device:
            return False
        timestamp = now()
        with db() as connection:
            connection.execute("""INSERT INTO participants VALUES(?,?,?,?)
                ON CONFLICT(session_name,device_id) DO UPDATE SET last_seen_at=excluded.last_seen_at""",
                               (name, device, timestamp, timestamp))
    clients[request.sid] = {"session": name, "role": role, "device": device}
    join_room(room(name))
    emit("state_update", state_for(record))

@socketio.on("disconnect")
def disconnected():
    clients.pop(request.sid, None)

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
