FROM python:3.12-slim

WORKDIR /app

# Inštalácia závislostí
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Zdrojový kód
COPY backend /app/backend
COPY frontend /app/frontend
COPY final_dataset.csv /app/
COPY entrypoint.sh /app/

EXPOSE 5000

# Štart (pozri entrypoint.sh): migrácie DB -> naplnenie DB -> gunicorn.
CMD ["sh", "entrypoint.sh"]
