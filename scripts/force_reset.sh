#!/usr/bin/sh

docker compose down -v
docker compose build

rm -rf ../backend/apps/accounts/migrations/*

docker compose run --rm backend python manage.py makemigrations
docker compose run --rm backend python manage.py migrate
docker compose run --rm backend python manage.py createsuperuser
docker compose up