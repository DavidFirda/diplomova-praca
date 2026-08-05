import pomdp_py
import random
import numpy as np
from scipy.special import softmax

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

class TutorPolicyModel(pomdp_py.PolicyModel):
    def __init__(self, categories, initial_temperature=1, min_temperature=0.05, decay_rate=0.98):
        self.categories = categories
        self.category_performance = {category: {"correct": 0, "incorrect": 0, "streak": 0} for category in categories} 
        self.temperature = initial_temperature  
        self.min_temperature = min_temperature  
        self.decay_rate = decay_rate  

    def update_performance(self, category, correct):
        if correct:
            self.category_performance[category]["correct"] += 1
            self.category_performance[category]["streak"] = 0  
        else:
            self.category_performance[category]["incorrect"] += 1
            self.category_performance[category]["streak"] += 1  
        
        self.temperature = max(self.min_temperature, self.temperature * self.decay_rate)

    def sample(self, belief):
        category_scores = {}

        for category in self.categories:
            stats = self.category_performance.get(category, {"correct": 0, "incorrect": 0})
            total = stats["correct"] + stats["incorrect"]
            accuracy = stats["correct"] / total if total > 0 else 0
            category_scores[category] = 1 - accuracy  * 2 

            belief_probability = sum(belief[state] for state in belief if isinstance(state, TutorState) and state.category == category)

            entropy = 0
            if 0 < belief_probability < 1:
                entropy = -belief_probability * np.log2(belief_probability + 1e-6) - (1 - belief_probability) * np.log2(1 - belief_probability + 1e-6)
            category_scores[category] += entropy  

        scores = np.array([category_scores[cat] for cat in self.categories])
        probabilities = softmax(scores / self.temperature)
        chosen_category = np.random.choice(self.categories, p=probabilities)

        return TutorAction(chosen_category)

class TutorBelief(pomdp_py.Histogram):
    
    def update(self, action, observation):
        updated_belief = {}

        for state in self:
            if state.category == action.category:
                likelihood = 0.8 if observation.correctness else 0.3
                updated_belief[state] = self[state] * likelihood
            else:
                updated_belief[state] = self[state]

        norm_factor = sum(updated_belief.values())
        if norm_factor > 0:
            for state in updated_belief:
                updated_belief[state] /= norm_factor

        self._hist = updated_belief


class TutorPOMDPv2(pomdp_py.POMDP):
    """ Hlavný POMDP model. """
    
    def __init__(self, categories):
        self.categories = categories
        init_category = random.choice(categories)
        init_level = 1
        init_state = TutorState(init_category, init_level)

        belief_distribution = {init_state: 1.0}
        
        agent = pomdp_py.Agent(
            TutorBelief(belief_distribution),  
            TutorPolicyModel(categories),  
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