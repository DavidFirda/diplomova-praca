import os

class Config:
    #SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/student_db")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_nqtZf7rg1Ayj@ep-yellow-breeze-a28p1csz-pooler.eu-central-1.aws.neon.tech/student_db?sslmode=require")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")