import os
import random
import json
from models import Question
from algorithms.storage import save_json
from algorithms.pomdp import BayesianTutorPOMDP, BayesianTutorBelief, TutorObservation, TutorAction, TutorState

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

            # belief (zoznam {category, level, p}) - obnov, ak je uložený
            saved_belief = saved.get("belief")
            if saved_belief:
                hist = {
                    TutorState(b["category"], b["level"]): b["p"]
                    for b in saved_belief
                }
                self.model.agent.set_belief(BayesianTutorBelief(hist), prior=True)

            # posledná zvolená akcia: selektor sa vytvára pri každom requeste,
            # preto sa pamätá v súbore (inak by update_after_answer stratil
            # akciu, ktorú select() vybral)
            last_cat = saved.get("last_action")
            if last_cat:
                self.last_action = TutorAction(last_cat)

    def _save_state(self):
        current_state = self.model.env.state
        save_data = {
            "policy": self.model.agent.policy_model.category_performance,
            "reward": self.model.env.reward_model.category_performance,
            "state": {
                "category": current_state.category,
                "level": current_state.knowledge_level
            },
            "belief": [
                {"category": st.category, "level": st.knowledge_level, "p": p}
                for st, p in self.model.agent.belief.histogram.items()
            ],
            "last_action": self.last_action.category if self.last_action else None,
        }
        save_json(self.model_path, save_data, indent=2)

    def select(self):
        self.last_action = self.model.agent.policy_model.sample(self.model.agent.belief)
        # ulož zvolenú akciu hneď - odpoveď môže spracovať iný proces/worker
        self._save_state()
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