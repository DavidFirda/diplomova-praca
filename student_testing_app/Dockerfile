
FROM python:3.12-slim 

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY backend /app/backend
COPY frontend /app/frontend
COPY final_dataset.csv /app/
COPY load_questions.py /app/

EXPOSE 5000

ENV FLASK_APP=backend/app.py


CMD ["sh", "-c", "-u","python load_questions.py && exec python backend/app.py"]

#EXPOSE 5000

#ENTRYPOINT ["sh", "-c"]
#CMD ["python load_questions.py && python backend/app.py"]
#CMD sh -c "python load_questions.py && exec gunicorn --chdir backend --bind 0.0.0.0:8080 app:application"
#ENV FLASK_APP=backend/app.py

# Run the app when the container starts
#CMD ["sh", "-c", "python load_questions.py && exec gunicorn --chdir backend --bind 0.0.0.0:5000 app:application"]

