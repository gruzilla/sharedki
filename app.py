from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from openai import OpenAI
import os
from threading import Lock
from dotenv import load_dotenv

app = Flask(__name__)
# First, try to read from existing environment variables
secret_key = os.environ.get("FLASK_SECRET")
openai_key = os.environ.get("OPENAI_API_KEY")
# If not found, load the .env file and then try again
if not openai_key:
    load_dotenv()  # This will set variables from .env if they're not already set
    openai_key = os.getenv("OPENAI_API_KEY")
    secret_key = os.getenv("FLASK_SECRET")

app.config['SECRET_KEY'] = secret_key
socketio = SocketIO(app)
# Set your OpenAI API Key
openAIClient = OpenAI(
    api_key=openai_key
)

def create_game_state():
    return {
        "currentQuestion": 0,
        "currentAnswers": [],
        "storedAnswers": {},  # {questionIndex: [list_of_answers]}
        "questions": ["Wie lautet der Name eurer Gruppe?", "Wo seid ihr gerade?"],
        "gamePhase": "collecting",
        "aiMode": "conversation",
        "gptModel": "gpt-5.6-terra",
        "systemPrompt": "You are a direct german teenager. Always answer in german. You represent a group of teenagers. Spare words, as if in a tv quiz show, no unnecessary phrases or introductions. Do not restate parts of the question in the answer. Do not quote your answer. If you are asked about personal questions like name, age, gender, make up an austrian teenager, aged 14, male, called Nikolaus living in vienna visiting a workshop in the Lila Raum in the Technisches Museum Wien."
    }


game_sessions = {}
client_sessions = {}


def normalize_session_name(name):
    if not isinstance(name, str):
        return ""
    return " ".join(name.strip().lower().split())


def get_game_state(session_name):
    return game_sessions.setdefault(session_name, create_game_state())


def session_from_http_request():
    session_name = normalize_session_name(request.args.get("session"))
    if not session_name:
        return None, (jsonify(success=False, error="Session name is required"), 400)
    return session_name, None


def session_room(session_name):
    return f"game:{session_name}"


# Independent mode reuses answers for identical requests.
ai_answer_cache = {}

# Conversation IDs stay server-side and are bound to a normalized game-session name.
openai_conversations = {}
ai_request_locks = {}


def get_ai_request_lock(session_name):
    return ai_request_locks.setdefault(session_name, Lock())


def get_openai_conversation_id(session_name, app_state):
    signature = (app_state["gptModel"], app_state["systemPrompt"])
    conversation_state = openai_conversations.get(session_name)

    if conversation_state and conversation_state["signature"] == signature:
        return conversation_state["id"]

    conversation = openAIClient.conversations.create(
        metadata={"game_session": session_name[:512]},
        items=[
            {
                "type": "message",
                "role": "system",
                "content": app_state["systemPrompt"],
            }
        ],
    )
    openai_conversations[session_name] = {
        "id": conversation.id,
        "signature": signature,
    }
    return conversation.id


def get_independent_ai_answer(app_state, question):
    cache_key = (
        app_state["gptModel"],
        app_state["systemPrompt"],
        question,
    )
    ai_answer = ai_answer_cache.get(cache_key)
    if ai_answer is not None:
        return ai_answer

    completion = openAIClient.chat.completions.create(
        model=app_state["gptModel"],
        messages=[
            {"role": "system", "content": app_state["systemPrompt"]},
            {"role": "user", "content": question},
        ],
        max_completion_tokens=150,
    )
    ai_answer = completion.choices[0].message.content.strip()
    ai_answer_cache[cache_key] = ai_answer
    return ai_answer


def get_conversation_ai_answer(session_name, app_state, question):
    conversation_id = get_openai_conversation_id(session_name, app_state)
    response = openAIClient.responses.create(
        model=app_state["gptModel"],
        conversation=conversation_id,
        input=[
            {
                "role": "user",
                "content": question,
            }
        ],
        max_output_tokens=150,
    )
    return response.output_text.strip()

@app.route('/')
def index():
    # Simple landing page listing roles
    return """
    <h1>Select Screen</h1>
    <ul>
      <li><a href="/presenter">Presenter Screen</a></li>
      <li><a href="/participant">Participant Screen</a></li>
      <li><a href="/admin">Admin Screen</a></li>
    </ul>
    """

@app.route('/presenter')
def presenter():
    return render_template('presenter.html')

@app.route('/participant')
def participant():
    return render_template('participant.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/admin/get_state', methods=['GET'])
def get_state():
    session_name, error = session_from_http_request()
    if error:
        return error
    return jsonify(get_game_state(session_name))


@app.route('/admin/clear_answers', methods=['POST'])
def clear_answers():
    session_name, error = session_from_http_request()
    if error:
        return error
    app_state = get_game_state(session_name)
    cq = app_state["currentQuestion"]

    if cq in app_state["storedAnswers"]:
        app_state["storedAnswers"][cq] = [
            answer for answer in app_state["storedAnswers"][cq]
            if answer not in app_state["currentAnswers"]
        ]
    app_state["currentAnswers"] = []
    socketio.emit('state_update', app_state, room=session_room(session_name))
    return jsonify(success=True)


@app.route('/admin/update_state', methods=['POST'])
def admin_update_state():
    session_name, error = session_from_http_request()
    if error:
        return error
    app_state = get_game_state(session_name)
    data = request.get_json() or {}
    requested_ai_mode = data.get("aiMode")
    if requested_ai_mode is not None and requested_ai_mode not in {
        "conversation",
        "independend",
    }:
        return jsonify(success=False, error="Invalid AI mode"), 400

    old_index = app_state["currentQuestion"]

    for key, value in data.items():
        if key == "currentQuestion" and value != old_index:
            if old_index not in app_state["storedAnswers"]:
                app_state["storedAnswers"][old_index] = []
            app_state["storedAnswers"][old_index].extend(app_state["currentAnswers"])
            app_state["currentAnswers"] = app_state["storedAnswers"].get(value, [])
        app_state[key] = value

    socketio.emit('state_update', app_state, room=session_room(session_name))
    return jsonify(success=True)


@socketio.on('connect')
def handle_connect(auth):
    session_name = normalize_session_name((auth or {}).get("session"))
    if not session_name:
        return False

    client_sessions[request.sid] = session_name
    join_room(session_room(session_name))
    emit('state_update', get_game_state(session_name))


@socketio.on('disconnect')
def handle_disconnect():
    client_sessions.pop(request.sid, None)


@socketio.on('participant_action')
def handle_participant_action(data):
    session_name = client_sessions.get(request.sid)
    if not session_name:
        return

    app_state = get_game_state(session_name)
    action = data.get("action")
    state_changed = False

    if action == "suggest_question":
        suggestion = data.get("question", "").strip()
        if suggestion and suggestion not in app_state["questions"]:
            app_state["questions"].append(suggestion)
            state_changed = True
    elif action == "submit_answer":
        answer = data.get("answer", "").strip()
        if answer:
            app_state["currentAnswers"].append(answer)
            state_changed = True
    elif action == "update_question":
        old_q = data.get("oldQuestion", "").strip()
        new_q = data.get("newQuestion", "").strip()
        if old_q and new_q:
            try:
                index = app_state["questions"].index(old_q)
                app_state["questions"][index] = new_q
                state_changed = True
            except ValueError:
                if new_q not in app_state["questions"]:
                    app_state["questions"].append(new_q)
                    state_changed = True

    if state_changed:
        socketio.emit('state_update', app_state, room=session_room(session_name))


@app.route('/admin/get_ai_answer', methods=['POST'])
def get_ai_answer():
    session_name, error = session_from_http_request()
    if error:
        return error
    app_state = get_game_state(session_name)
    cq = app_state["currentQuestion"]

    if not 0 <= cq < len(app_state["questions"]):
        return jsonify(success=False, error="Invalid question index"), 400
    question = app_state["questions"][cq]

    with get_ai_request_lock(session_name):
        try:
            if app_state["aiMode"] == "conversation":
                ai_answer = get_conversation_ai_answer(
                    session_name,
                    app_state,
                    question,
                )
            else:
                ai_answer = get_independent_ai_answer(app_state, question)
        except Exception as e:
            return jsonify(success=False, error=str(e)), 500

        app_state["currentAnswers"].append(ai_answer)
    socketio.emit('state_update', app_state, room=session_room(session_name))
    return jsonify(success=True, answer=ai_answer)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0')
