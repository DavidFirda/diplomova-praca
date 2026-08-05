import os

class Config:
    # DATABASE_URL sa načíta z .env (pozri .env.example). Pre lokálny Docker beh
    # ukazuje default na lokálnu Postgres službu "db" z docker-compose.yml.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql://student_user:student_pass@db:5432/student_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")