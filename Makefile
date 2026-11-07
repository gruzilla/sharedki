# Variables
DOCKER_COMPOSE_FILE = docker-compose.yml
DEVELOPMENT_DOCKER_COMPOSE_FILE = development-docker-compose.yml

.PHONY: all dev build up down clean logs restart install-dev format lint

# Default target
all: build up

# Start a local development server with live code reloading
dev:
	docker-compose -f $(DEVELOPMENT_DOCKER_COMPOSE_FILE) up --build

# Build the Docker containers
build:
	docker-compose -f $(DOCKER_COMPOSE_FILE) build

# Start the Docker Compose services
up:
	docker-compose -f $(DOCKER_COMPOSE_FILE) up -d

# Stop the Docker Compose services
down:
	docker-compose -f $(DOCKER_COMPOSE_FILE) down

# Stop and remove all containers, networks, and volumes
clean:
	docker-compose -f $(DOCKER_COMPOSE_FILE) down -v --rmi all

# View logs from the running containers
logs:
	docker-compose -f $(DOCKER_COMPOSE_FILE) logs -f

# Restart the services (useful after code changes)
restart: down up

# Install frontend linting and formatting tools
install-dev:
	python3 -m pip install -r requirements-dev.txt

# Format Jinja/HTML, JavaScript, and CSS
format:
	python3 tools/frontend_quality.py

# Check frontend formatting and lint Jinja/HTML
lint:
	python3 tools/frontend_quality.py --check
