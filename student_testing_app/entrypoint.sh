#!/bin/sh

set -e
cd /app/backend

flask --app app db upgrade      
flask --app app bootstrap      

exec gunicorn --bind 0.0.0.0:5000 \
     --workers "${GUNICORN_WORKERS:-4}" --threads "${GUNICORN_THREADS:-2}" \
     --timeout 120 app:app
