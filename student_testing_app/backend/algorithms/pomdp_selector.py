import os
import random
import json
from models import Question
from algorithms.pomdp import BayesianTutorPOMDP, TutorObservation, TutorAction, TutorState

class POMDPQuestionSelector:
    def __init__(self, student_id, test_session, categories, excluded_ids=None):
        self.student_id = student_id
        self.test_session = test_session
        self.categories = categories
        self.excluded_ids = excluded_ids or []
        self.model_path = os.path.join("data/pomdp", f"pomdp_{student_id}_{test_session}.json")
        self.model = BayesianTutorPOMDP(categories)
        self.last_action = None
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.model_path):
            with open(self.model_path, "r") as f:
                saved = json.load(f)

            for cat, val in saved.get("policy", {}).items():
                self.model.agent.policy_model.category_performance[cat] = val

            for cat, val in saved.get("reward", {}).items():
                self.model.env.reward_model.category_performance[cat] = val

            state_cat = saved.get("state", {}).get("category")
            state_lvl = saved.get("state", {}).get("level")
            if state_cat and state_lvl:
                self.model.env.set_state(TutorState(state_cat, state_lvl))

    def _save_state(self):
        current_state = self.model.env.state
        save_data = {
            "policy": self.model.agent.policy_model.category_performance,
            "reward": self.model.env.reward_model.category_performance,
            "state": {
                "category": current_state.category,
                "level": current_state.knowledge_level
            }
        }
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        with open(self.model_path, "w") as f:
            json.dump(save_data, f, indent=2)

    def select(self):
        self.last_action = self.model.agent.policy_model.sample(self.model.agent.belief)
        category = self.last_action.category
        questions = Question.query.filter(
            Question.category == category,
            ~Question.id.in_(self.excluded_ids)
        ).all()
        return random.choice(questions) if questions else None

    def update_after_answer(self, question_id, category, correct):
        obs = TutorObservation(correct)
        if self.last_action is None:
            self.last_action = TutorAction(category)
        self.model.step_with_action(self.last_action, obs)
        self._save_state()