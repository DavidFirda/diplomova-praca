DO $$ 
BEGIN 
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'student_db') THEN 
      CREATE DATABASE student_db;
   END IF;
END $$;

\c student_db

-- Študenti
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    login VARCHAR(50) UNIQUE NOT NULL
);

-- Otázky
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    instruction TEXT NOT NULL,
    input_data TEXT,
    output TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    subcategory VARCHAR(100),
    incorrect_output TEXT
);

-- Odpovede
CREATE TABLE student_answers (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id),
    question_id INTEGER REFERENCES questions(id),
    category VARCHAR(100) NOT NULL,
    answer_code TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    test_type VARCHAR NOT NULL,
    test_session VARCHAR
);

-- Zhrnutia
CREATE TABLE test_summaries (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id),
    test_type VARCHAR NOT NULL,
    test_session VARCHAR,
    category VARCHAR NOT NULL,
    total_answers INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    incorrect_answers INTEGER DEFAULT 0
);

--Dotazník
CREATE TABLE student_feedback (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id),
    gender VARCHAR(20),
    age INTEGER,
    experience VARCHAR(50),
    field_of_study VARCHAR(100),
    understand_questions VARCHAR(20),
    easy_navigation VARCHAR(20),
    motivation_level VARCHAR(20),
    helpful_feedback VARCHAR(20),
    overall_usefulness VARCHAR(20),
    difficulty_match VARCHAR(20),
    improved_skills VARCHAR(20),
    time_spent VARCHAR(50),
    future_interest VARCHAR(20),
    ui_satisfaction VARCHAR(20),
    improvement_suggestion TEXT
);