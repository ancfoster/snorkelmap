#!/bin/sh
# Dokploy runs this on every container start (i.e. after every deploy
# triggered by a push to GitHub, and on any restart). It applies
# outstanding migrations before gunicorn starts serving, so a deploy
# that includes a schema change never serves against the old schema.
#
# Deliberately NOT running makemigrations here: migration files belong
# in the repo, generated and reviewed in development, not invented
# against whatever the production models happen to look like at
# deploy time. If Dokploy starts a second replica of this container in
# future, this also needs to become a single pre-deploy step rather
# than a per-container one, since concurrent `migrate` runs on the same
# database are not safe.
set -e

echo "[entrypoint] applying migrations..."
python manage.py migrate --noinput

echo "[entrypoint] starting gunicorn..."
exec gunicorn snorkelmap.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 120
