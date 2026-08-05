import pomdp_py
import random
import numpy as np
from scipy.stats import beta

class TutorState(pomdp_py.State):
    """ Stav študenta – úroveň znalostí v kategórii. """
    def __init__(self, category, knowledge_level):
        self.category = category
        self.knowledge_level = knowledge_level
    
    def __hash__(self):
        return hash((self.category, self.knowledge_level))
    
    def __eq__(self, other):
        return self.category == other.category and self.knowledge_level == other.knowledge_level

class TutorAction(pomdp_py.Action):
    """ Výber otázky v určitej kategórii. """
    def __init__(self, category):
        self.category = category
    
    def __hash__(self):
        return hash(self.category)

class TutorObservation(pomdp_py.Observation):
    """ Správna alebo nesprávna odpoveď študenta. """
    def __init__(self, correctness):
        self.correctness = correctness
    
class TutorEnvironment(pomdp_py.Environment):
    def __init__(self, init_state, transition_model, reward_model):
        super().__init__(init_state, transition_model, reward_model)
    
    def set_state(self, new_state):
        self._state = new_state    

class TutorTransitionModel(pomdp_py.TransitionModel):
    """
    TutorTransitionModel (Model prechodu stavov)
    Zlepšená pravdepodobnosť učenia:
        - 80 % pravdepodobnosť, že sa znalosti zvýšia.
        - 10 % pravdepodobnosť, že ostanú rovnaké.
        - 20 % pravdepodobnosť, že sa znížia (ak odpoveď bola nesprávna).
    """
    def sample(self, state, action):
        if state.category == action.category:
            if state.knowledge_level == 3:
                return state  #
            
            if random.random() < 0.8:
                return TutorState(state.category, min(3, state.knowledge_level + 1))
            elif random.random() < 0.1:
                return state
            else:
                return TutorState(state.category, max(1, state.knowledge_level - 1))
        return state

class TutorObservationModel(pomdp_py.ObservationModel):
    """
    Definuje, aká je pravdepodobnosť správnej odpovede.
    Ak má študent vyššiu úroveň znalostí (>1), odpovie správne s 80 % pravdepodobnosťou.
    Ak má študent nízku úroveň znalostí (≤1), odpovie správne iba s 40 % pravdepodobnosťou.
    """
    def sample(self, next_state, action):
        if next_state.knowledge_level > 1:
            return TutorObservation(True) if random.random() < 0.8 else TutorObservation(False)
        else:
            return TutorObservation(True) if random.random() < 0.4 else TutorObservation(False)

class TutorRewardModel(pomdp_py.RewardModel):
    
    def __init__(self):
        self.category_performance = {}

    def update_performance(self, category, correct):
        if category not in self.category_performance:
            self.category_performance[category] = {"correct": 0, "incorrect": 0}
        if correct:
            self.category_performance[category]["correct"] += 1
        else:
            self.category_performance[category]["incorrect"] += 1

    def reward(self, state, action, next_state):
        accuracy = self.get_accuracy(action.category)
        weak = accuracy < 0.6

        if next_state.knowledge_level > state.knowledge_level:
            return 15 if weak else 10
        elif next_state.knowledge_level == state.knowledge_level:
            return -1
        else:
            return -10 if weak else -5

    def get_accuracy(self, category):
        stats = self.category_performance.get(category, {"correct": 0, "incorrect": 0})
        total = stats["correct"] + stats["incorrect"]
        return stats["correct"] / total if total > 0 else 1.0 


class BayesianTutorPolicy(pomdp_py.PolicyModel):
    """
    Bayesovská politika s dôrazom na viaceré slabé kategórie.
    Používa Beta distribúciu na modelovanie úspešnosti.
    Pri výbere otázky sa využíva Thompson Sampling s viacerými slabými kategóriami.
    """

    def __init__(self, categories, weak_threshold=0.6):
        self.categories = categories
        self.weak_threshold = weak_threshold
        self.category_performance = {category: {"alpha": 1, "beta": 1} for category in categories}

    def update_performance(self, category, correct, decay=0.95):
        """Bayesovská aktualizácia s poklesom vplyvu starých údajov.
           Každá kategória má svoju Beta distribúciu: Beta(alpha, beta), kde `alpha` reprezentuje počet správnych odpovedí a `beta` počet nesprávnych odpovedí.
            Pri každej novej odpovedi:
            - Všetky predchádzajúce odpovede sú "zabudnuté" pomocou faktora `decay`(napr. 0.95 = pamätá si ~95 % váhy z minulosti).
            - Potom sa započíta nová odpoveď ako +1 do správnych alebo nesprávnych.
            Výsledkom je, že novšie odpovede majú väčší vplyv na model než tie staršie.    
        """
        if category not in self.category_performance:
            self.category_performance[category] = {"alpha": 1, "beta": 1}

        self.category_performance[category]["alpha"] *= decay
        self.category_performance[category]["beta"] *= decay

        if correct:
            self.category_performance[category]["alpha"] += 1
        else:
            self.category_performance[category]["beta"] += 1

    def get_category_strength(self, category):
        """ Odhad úspešnosti kategórie s váženou pravdepodobnosťou.
            Vypočíta sa:
                - `estimated_prob`: priemerná úspešnosť podľa Beta rozdelenia.
                - `weight`: koľko "veríme" tejto pravdepodobnosti — viac pokusov → vyššia váha.
                - `weighted_prob`: kombinácia odhadu a prednastavenej hodnoty (0.5), ktorá slúži ako základný predpoklad, keď máme málo dát.
            To zabezpečuje:
                - Stabilitu pri malom počte odpovedí.
                - Viac dôvery v model, ak má dostatok údajov.
        """
        alpha = self.category_performance[category]["alpha"]
        beta = self.category_performance[category]["beta"]
        # Odhadovaná pravdepodobnosť správnej odpovede
        estimated_prob = alpha / (alpha + beta)
        total_attempts = alpha + beta

        weight = total_attempts / (total_attempts + 2)  # 2 je smoothing parameter
        weighted_prob = weight * estimated_prob + (1 - weight) * 0.5
    
        return weighted_prob
    
    def identify_weak_categories(self):
        """Nájde slabé kategórie a zvýhodní extrémne slabé."""
        weak_categories = []

        for cat in self.categories:
            strength = self.get_category_strength(cat)
            if strength < self.weak_threshold:
                weak_categories.append((cat, strength))

        return [cat[0] for cat in weak_categories]  # Vrátime len názvy kategórií

    def sample(self, belief):
        """Používa vážené Thompson Sampling so všetkými slabými kategóriami."""

        # Generujeme Thompson Sampling pravdepodobnosti pre všetky kategórie
        sampled_probs = {category: beta.rvs(self.category_performance[category]["alpha"], 
                                            self.category_performance[category]["beta"])
                        for category in self.categories}

        weak_categories = self.identify_weak_categories()

        if weak_categories:
            # Vyberieme otázku z viacerých slabých kategórií s pravdepodobnosťou úmernou slabosti
            weak_probs = np.array([1 - self.get_category_strength(cat) for cat in weak_categories])
            weak_probs /= weak_probs.sum()  # Normalizujeme pravdepodobnosti na jednotku

            best_category = np.random.choice(weak_categories, p=weak_probs)
            self.focus_category = best_category
            self.focus_counter = 1
            return TutorAction(best_category)
        else:
            # Ak nie sú slabé kategórie, normálne Thompson Sampling
            self.focus_category = None
            self.focus_counter = 0
            best_category = max(sampled_probs, key=sampled_probs.get)
            return TutorAction(best_category)


class BayesianTutorBelief(pomdp_py.Histogram):
    def update(self, action, observation):
        """ Aktualizácia belief pomocou Bayesovskej inferencie. """
        updated_belief = {}

        for state in self:
            if state.category == action.category:
                prob_correct = 0.8 if state.knowledge_level > 1 else 0.3
                likelihood = prob_correct if observation.correctness else (1 - prob_correct)
                updated_belief[state] = self[state] * likelihood
            else:
                updated_belief[state] = self[state]

        norm_factor = sum(updated_belief.values())
        if norm_factor > 0:
            for state in updated_belief:
                updated_belief[state] /= norm_factor

        self._hist = updated_belief

class BayesianTutorPOMDP(pomdp_py.POMDP):
    """ Hlavný POMDP model s Bayesovskou politikou a lepším zameraním na viaceré slabé kategórie. """

    def __init__(self, categories):
        self.categories = categories
        init_category = random.choice(categories)
        init_level = 1
        init_state = TutorState(init_category, init_level)

        belief_distribution = {init_state: 1.0}
        
        agent = pomdp_py.Agent(
            BayesianTutorBelief(belief_distribution),  
            BayesianTutorPolicy(categories),  
            TutorTransitionModel(),
            TutorObservationModel(),
            TutorRewardModel()
        )
        env = TutorEnvironment(init_state, TutorTransitionModel(), TutorRewardModel())
        super().__init__(agent, env)
    
    def step(self, student_model, category):
        action = TutorAction(category)
        correct = student_model.answer_question(category)
        observation = TutorObservation(correct)
        
        next_state = self.env.transition_model.sample(self.env.state, action)
        reward = self.env.reward_model.reward(self.env.state, action, next_state)

        self.env.set_state(next_state)
        self.agent.policy_model.update_performance(category, correct)
        self.agent.belief.update(action, observation)

        return observation, reward
    