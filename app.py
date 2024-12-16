from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import json
from openai import OpenAI
import os
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

# Global application state
global app_state;
app_state = {
    "currentQuestion": 0,
    "currentAnswers": [],
    "storedAnswers": {},  # {questionIndex: [list_of_answers]}
    "questions": ["Wie lautet der Name eurer Gruppe?", "Wo seid ihr gerade?"],
    "gamePhase": "collecting",  # new state: either "collecting" or "answering"
    "gptModel": "gpt-3.5-turbo",
    "systemPrompt": "You are a direct german teenager. Always answer in german. You represent a group of teenagers. Spare words, as if in a tv quiz show, no unnecessary phrases or introductions. Do not restate parts of the question in the answer. Do not quote your answer. If you are asked about personal questions like name, age, gender, make up an austrian teenager, aged 14, male, called Nikolaus living in vienna visiting a workshop in the Lila Raum in the Technisches Museum Wien."
}

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
    global app_state
    return jsonify(app_state)

@app.route('/admin/clear_answers', methods=['POST'])
def clear_answers():
    global app_state
    cq = app_state["currentQuestion"]
    # Only remove currentAnswers from storedAnswers for the currentQuestion
    if cq in app_state["storedAnswers"]:
        # Filter out any answer currently in currentAnswers
        app_state["storedAnswers"][cq] = [
            ans for ans in app_state["storedAnswers"][cq] 
            if ans not in app_state["currentAnswers"]
        ]
    # Clear the currentAnswers
    app_state["currentAnswers"] = []
    socketio.emit('state_update', app_state)
    return jsonify(success=True)

# REST endpoint for admin to update global state (e.g. currentQuestion)
@app.route('/admin/update_state', methods=['POST'])
def admin_update_state():
    global app_state
    # Expecting JSON with keys to update, for example: {"currentQuestion": 1}
    data = request.get_json()
    old_index = app_state["currentQuestion"]

    for key, value in data.items():
        # If the currentQuestion is being updated, before we actually change it,
        # move currentAnswers to storedAnswers and clear currentAnswers.
        if key == "currentQuestion" and value != old_index:
            # Move currentAnswers to storedAnswers for the old question index
            if old_index not in app_state["storedAnswers"]:
                app_state["storedAnswers"][old_index] = []
            app_state["storedAnswers"][old_index].extend(app_state["currentAnswers"])

            # Load answers for the new question index, or empty if none exist
            app_state["currentAnswers"] = app_state["storedAnswers"].get(value, [])

        # Update the state
        app_state[key] = value
    # Broadcast the new state to all connected clients
    socketio.emit('state_update', app_state)
    return jsonify(success=True)

# On client connect, send the current state
@socketio.on('connect')
def handle_connect():
    global app_state
    emit('state_update', app_state)

# Example event to handle participant suggestions or answers from clients
@socketio.on('participant_action')
def handle_participant_action(data):
    global app_state
    # data might be something like {"action": "suggest_question", "question": "Some question..."}
    action = data.get("action")
    if action == "suggest_question":
        suggestion = data.get("question", "")
        if suggestion.strip() and suggestion not in app_state["questions"]:
            app_state["questions"].append(suggestion)
            socketio.emit('state_update', app_state)
    elif action == "submit_answer":
        answer = data.get("answer", "")
        if answer.strip():
            app_state["currentAnswers"].append(answer)
            socketio.emit('state_update', app_state)
    elif action == "update_question":
        old_q = data.get("oldQuestion", "").strip()
        new_q = data.get("newQuestion", "").strip()

        if old_q and new_q:
            # Attempt to find the old question in the list
            try:
                idx = app_state["questions"].index(old_q)
                app_state["questions"][idx] = new_q
                socketio.emit('state_update', app_state)
            except ValueError:
                # old_q not found in the list, you might want to handle this case
                pass

    # Additional participant actions could be handled here.

@app.route('/admin/get_ai_answer', methods=['POST'])
def get_ai_answer():
    global app_state
    # Get the current question
    cq = app_state["currentQuestion"]
    if cq < len(app_state["questions"]):
        question = app_state["questions"][cq]
    else:
        return jsonify(success=False, error="Invalid question index"), 400

    # Call the OpenAI API to get an answer (example using gpt-3.5-turbo)
    try:
        completion = openAIClient.chat.completions.create(
            model=app_state["gptModel"],
            messages=[{"role": "system", "content": app_state["systemPrompt"]},
                      {"role": "user", "content": question}],
            max_tokens=150,
            temperature=0.7
        )
        print(completion)
        ai_answer = completion.choices[0].message.content.strip()
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

    # Store the AI answer - for example, append to currentAnswers or storedAnswers
    app_state["currentAnswers"].append(ai_answer)
    socketio.emit('state_update', app_state)
    return jsonify(success=True, answer=ai_answer)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0')