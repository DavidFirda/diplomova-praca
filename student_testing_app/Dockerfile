FROM python:3.12-slim

WORKDIR /app

# Inštalácia závislostí
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Zdrojový kód
COPY backend /app/backend
COPY frontend /app/frontend
COPY final_dataset.csv /app/
COPY load_questions.py /app/

EXPOSE 5000

ENV FLASK_APP=backend/app.py

# Štart: najprv načíta otázky, potom spustí gunicorn.
# --chdir backend => modul "app" sa hľadá v priečinku backend (app.py -> objekt "app")
# --workers 4 zvláda súbežné požiadavky; rate limiter je zdieľaný cez Redis,
#   takže limity platia naprieč všetkými workermi.
CMD ["sh", "-c", "python load_questions.py && exec gunicorn --chdir backend --bind 0.0.0.0:5000 --workers 4 --threads 2 --timeout 120 app:app"]
