# Shared KI / CyberQuest

CyberQuest is a browser-based classroom game in which groups of students propose questions, submit answers, and try to distinguish human responses from an AI-generated response. It combines the shared-screen party format of *The Jackbox Party Pack* with the fast classroom participation of *Kahoot!* and a little of the bluffing and deduction found in *Balderdash*.

A teacher prepares and protects a game session with a private PIN, starts the live round, and controls the current question and game phase. Students join from their own devices with the public session ID, while a separate presenter view can be shown on a classroom display. When the game ends, CyberQuest creates a printable report with the questions, AI and participant answers, duplicate responses, game duration, and participant count.

Game sessions and results are persisted in SQLite. Opening a report also writes a timestamped JSON snapshot to the local `savegames/` directory.

## Run the development version locally

### Prerequisites

Install:

- Docker
- Docker Compose
- An OpenAI API key

No local Python installation is required to run the application in Docker.

### 1. Configure the environment

Create a `.env` file in the project root:

```dotenv
OPENAI_API_KEY=your-openai-api-key
FLASK_SECRET=replace-this-with-a-long-random-secret
```

Use a unique, unpredictable value for `FLASK_SECRET`. Do not commit the `.env` file.

Ensure the report snapshot directory exists:

```sh
mkdir -p savegames
```

### 2. Start the development server

Using the Makefile:

```sh
make dev
```

The Makefile uses the Docker Compose plugin. The equivalent command without Make is:

```sh
docker compose -f development-docker-compose.yml up --build
```

The development container mounts the source directory into the container and runs Flask in debug mode, so Python and template changes reload automatically.

### 3. Open the application

Visit [http://127.0.0.1:5000](http://127.0.0.1:5000).

The main screens are:

- Teacher: [http://127.0.0.1:5000/admin](http://127.0.0.1:5000/admin)
- Participant: [http://127.0.0.1:5000/participant](http://127.0.0.1:5000/participant)
- Presenter: [http://127.0.0.1:5000/presenter](http://127.0.0.1:5000/presenter)

Create a session in the teacher view, choose a private teacher PIN, prepare the game, and select **Start live game** before students or the presenter try to join.

### 4. Stop the server

Press `Ctrl+C` in the terminal running Docker Compose.

The development SQLite database is stored in the Docker volume `cyberquest_dev_data`. JSON report snapshots remain available in the project’s `savegames/` directory.

To remove the development container and its SQLite volume:

```sh
docker compose -f development-docker-compose.yml down -v
```

This deletes locally persisted development sessions, participants, and answers.

## Frontend formatting

Install the development tooling and check the frontend:

```sh
make install-dev
make lint
```

Format Jinja/HTML templates, JavaScript, and CSS with:

```sh
make format
```

See [FORMATTING.md](FORMATTING.md) for details.
