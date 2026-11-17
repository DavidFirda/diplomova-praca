# ============================================================
# AdaptPy - POMDP selektor pre ÚLOHY (samoštúdium).
#
# Rovnaký POMDP ako pri hlavnom teste (algorithms/pomdp.py), len:
#  - stav sa drží v samostatnom súbore pomdp_<id>_ulohy.json (nemieša sa s testami),
#  - pri prvom vytvorení sa politika "zahreje" z doterajších odpovedí študenta
#    (predtest, testy), takže hneď vie, ktoré kategórie študent zvláda slabšie,
#  - výber otázky vie ustúpiť, keď v kategórii došli nevidené otázky,
#  - výsledok úlohy sa odovzdáva ako pozorovanie + odmena; neúspešná úloha
#    (5 nesprávnych pokusov) má pevne zápornú odmenu a stav sa nezlepší.
# ============================================================
import os
import random

from algorithms.pomdp import TutorAction, TutorObservation, TutorState
from algorithms.pomdp_selector import POMDPQuestionSelector
from models import Question

TASK_SESSION = "ulohy"
FAILED_TASK_REWARD = -10.0     # odmena POMDP za úlohu, ktorú študent nevyriešil


class POMDPTaskSelector(POMDPQuestionSelector):
    def __init__(self, student_id, categories, excluded_ids=None,
                 fallback_excluded_ids=None, history=None):
        """
        excluded_ids          - otázky, ktoré sa majú vynechať (už videné),
        fallback_excluded_ids - prísnejšia záloha: čo sa vynechá, ak nevidené došli,
        history               - [(kategória, správne?)] doterajších odpovedí študenta
                                (použije sa len pri prvom vytvorení stavu).
        """
        self.fallback_excluded_ids = list(fallback_excluded_ids or [])
        self.rewards = {"count": 0, "total": 0.0, "last": None}
        super().__init__(student_id, TASK_SESSION, categories, excluded_ids)
        if not os.path.exists(self.model_path):
            self._warm_start(history or [])
            self._save_state()

    # --- stav v súbore navyše: súhrn odmien ---
    def _restore_extra(self, saved):
        rewards = saved.get("rewards")
        if isinstance(rewards, dict):
            self.rewards.update(rewards)

    def _extra_state(self):
        return {"rewards": self.rewards}

    # --- zahriatie politiky z histórie ---
    def _warm_start(self, history):
        policy = self.model.agent.policy_model
        reward_model = self.model.env.reward_model
        for category, correct in history:
            if category in self.categories:
                policy.update_performance(category, bool(correct))
                reward_model.update_performance(category, bool(correct))

    # --- výber úlohy ---
    def _pick(self, category, excluded):
        ids = [row[0] for row in Question.query.filter(
            Question.category == category, ~Question.id.in_(excluded)
        ).with_entities(Question.id).all()]
        return Question.query.get(random.choice(ids)) if ids else None

    def select(self):
        """
        (otázka, úroveň) kde úroveň 'fresh' = nevidená otázka, 'repeat' = už videná
        (záloha), 'other_category' = kategória, ktorú POMDP nevybral. (None, None),
        ak nie je z čoho vyberať.
        """
        self.last_action = self.model.agent.policy_model.sample(self.model.agent.belief)
        self._save_state()
        chosen = self.last_action.category

        for excluded, level in ((self.excluded_ids, "fresh"), (self.fallback_excluded_ids, "repeat")):
            question = self._pick(chosen, excluded)
            if question is not None:
                return question, level

        for category in self.categories:
            if category == chosen:
                continue
            for excluded in (self.excluded_ids, self.fallback_excluded_ids):
                question = self._pick(category, excluded)
                if question is not None:
                    return question, "other_category"
        return None, None

    # --- výsledok úlohy -> POMDP ---
    def update_after_task(self, category, correct, failed=False, credit=1.0):
        """
        Odovzdá výsledok úlohy POMDP a vráti odmenu.
          správne         -> pozorovanie "správne", odmena podľa modelu (prechod stavov),
          failed (5 chýb) -> pozorovanie "nesprávne", pevne záporná odmena a stav sa
                             nezlepší (kategória sa tým označí ako slabšia).
          credit (0-1)    -> vyriešené s nápovedami (HINT_CREDIT v task_flow): výkon v kategórii
                             sa aktualizuje len čiastočne (alpha += credit, beta += 1 - credit),
                             kladná odmena sa zníži v rovnakom pomere; pri credit < 0,5 (3 nápovedy)
                             sa pozorovanie berie ako "nesprávne" a stav sa nezlepší.
        """
        action = TutorAction(category)
        credit = 1.0 if credit is None else max(0.0, min(float(credit), 1.0))
        if not failed and correct and credit < 1.0:
            state = self.model.env.state
            observed_correct = credit >= 0.5
            next_state = None if observed_correct else state
            _, reward = self.model.step_with_action(
                action, TutorObservation(observed_correct), next_state=next_state, weight=credit,
            )
            if reward > 0:
                reward = round(reward * credit, 4)
        elif failed:
            state = self.model.env.state
            next_state = state
            if state.category == category:
                next_state = TutorState(state.category, max(1, state.knowledge_level - 1))
            _, reward = self.model.step_with_action(
                action, TutorObservation(False), reward=FAILED_TASK_REWARD, next_state=next_state,
            )
        else:
            _, reward = self.model.step_with_action(action, TutorObservation(bool(correct)))

        self.rewards["count"] += 1
        self.rewards["total"] = round(self.rewards["total"] + float(reward), 4)
        self.rewards["last"] = float(reward)
        self.last_action = None
        self._save_state()
        return float(reward)
