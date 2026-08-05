import random

class RandomQuestionSelector:
    def __init__(self, categories, weak_categories):
        self.categories = list(categories)
        self.weak_categories = list(weak_categories)

    def select_random_question(self):
        return random.choice(self.categories)
