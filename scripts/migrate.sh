#!/usr/bin/env sh

docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm backend python manage.py makemigrations

docker compose -f docker-compose.yml -f docker-compose.dev.yml run --rm backend python manage.py migrate
