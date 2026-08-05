import random
from models import Question
from algorithms.q_learning import QLearning
import os

class QLearningQuestionSelector:
    def __init__(self, student_id, categories, test_session ,excluded_ids=None):
        self.student_id = student_id
        self.categories = categories
        self.excluded_ids = excluded_ids or []
        self.test_session = test_session

        q_table_file = os.path.join("data/q_learning", f"q_table_{student_id}_{test_session}.json")
        log_file = os.path.join("data/q_learning", f"log_{student_id}_{test_session}.csv")

        self.qlearner = QLearning(
            categories=categories,
            q_table_file=q_table_file,
            log_file=log_file
        )
        self.qlearner.load_q_table()

    def select(self):
        category = self.qlearner.select_category()

        questions = Question.query.filter(
            Question.category == category,
            ~Question.id.in_(self.excluded_ids)
        ).all()

        return random.choice(questions) if questions else None

    def update_after_answer(self, question_id, category, correct):
        reward = self.qlearner.reward(category, correct)
        self.qlearner.update_q_value(
            question_ID=question_id,
            category=category,
            reward=reward,
            question_order=question_id
        )
        self.qlearner.decay_epsilon()
        self.qlearner.save_q_table()


    