import random
from models import Question

class RandomQuestionSelector:
    def __init__(self, categories, excluded_ids=None):
        self.categories = categories
        self.excluded_ids = excluded_ids or []

    def select(self):
        if not self.categories:
            return None

        selected_category = random.choice(self.categories)

        question = (
            Question.query
            .filter(Question.category == selected_category,
                    ~Question.id.in_(self.excluded_ids))
        ).all()
        return random.choice(question) if question else None