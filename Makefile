# Variables
DOCKER_COMPOSE_FILE = docker-compose.yml

# Default target
.PHONY: all
all: build up

# Build the Docker containers
.PHONY: build
build:
	docker-compose -f $(DOCKER_COMPOSE_FILE) build

# Start the Docker Compose services
.PHONY: up
up:
	docker-compose -f $(DOCKER_COMPOSE_FILE) up -d

# Stop the Docker Compose services
.PHONY: down
down:
	docker-compose -f $(DOCKER_COMPOSE_FILE) down

# Stop and remove all containers, networks, and volumes
.PHONY: clean
clean:
	docker-compose -f $(DOCKER_COMPOSE_FILE) down -v --rmi all

# View logs from the running containers
.PHONY: logs
logs:
	docker-compose -f $(DOCKER_COMPOSE_FILE) logs -f

# Restart the services (useful after code changes)
.PHONY: restart
restart: down up