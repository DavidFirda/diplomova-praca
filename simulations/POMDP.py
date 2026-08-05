import pomdp_py
import random

class TutorState(pomdp_py.State):
    """
    TutorState (Stav)
    Reprezentuje stav študenta – teda jeho úroveň znalostí v konkrétnej kategórii.
    """
    def __init__(self, category, knowledge_level):
        self.category = category
        self.knowledge_level = knowledge_level
    
    def __hash__(self):
        return hash((self.category, self.knowledge_level))
    
    def __eq__(self, other):
        return self.category == other.category and self.knowledge_level == other.knowledge_level

    def __str__(self):
        return f"State({self.category}, Level: {self.knowledge_level})"

class TutorAction(pomdp_py.Action):
    """"
    TutorAction (Akcia)
    Reprezentuje akciu tutora – teda výber kategórie otázky.
    """
    def __init__(self, category):
        self.category = category
    
    def __hash__(self):
        return hash(self.category)
    
    def __eq__(self, other):
        return self.category == other.category
    
    def __str__(self):
        return f"Action({self.category})"

class TutorObservation(pomdp_py.Observation):
    """
    Reprezentuje odpoveď študenta – správna alebo nesprávna.
    """
    def __init__(self, correctness):
        self.correctness = correctness
    
    def __hash__(self):
        return hash(self.correctness)
    
    def __eq__(self, other):
        return self.correctness == other.correctness
    
    def __str__(self):
        return f"Observation(Correct: {self.correctness})"
    
class TutorEnvironment(pomdp_py.Environment):
    def __init__(self, init_state, transition_model, reward_model):
        super().__init__(init_state, transition_model, reward_model)
    
    def set_state(self, new_state):
        self._state = new_state    

class TutorTransitionModel(pomdp_py.TransitionModel):
    """
    TutorTransitionModel (Model prechodu stavov)
    Definuje, ako sa mení znalosť študenta na základe položených otázok.
        Ak tutor položí otázku v tej istej kategórii:
        70 % pravdepodobnosť, že sa znalosti zvýšia.
        20 % pravdepodobnosť, že ostanú rovnaké.
        10 % pravdepodobnosť, že sa znížia.
        Ak otázka patrí inej kategórii, znalosti sa nemenia.
    """
    def sample(self, state, action):
        if state.category == action.category:
            if state.knowledge_level == 3:
                return state  # Ak je znalosť na maxime, ďalšia otázka ju už nemení
            
            if random.random() < 0.7:
                return TutorState(state.category, min(3, state.knowledge_level + 1))
            elif random.random() < 0.2:
                return state
            else:
                return TutorState(state.category, max(1, state.knowledge_level - 1))
        return state

class TutorObservationModel(pomdp_py.ObservationModel):
    """
    Definuje, aká je pravdepodobnosť správnej odpovede.
    Ak má študent vyššiu úroveň znalostí (>1), odpovie správne s 80 % pravdepodobnosťou.
    Ak má študent nízku úroveň znalostí (≤1), odpovie správne iba s 30 % pravdepodobnosťou.
    """
    def sample(self, next_state, action):
        if next_state.knowledge_level > 1:
            return TutorObservation(True) if random.random() < 0.8 else TutorObservation(False)
        else:
            return TutorObservation(True) if random.random() < 0.3 else TutorObservation(False)

class TutorRewardModel(pomdp_py.RewardModel):
    """
    Automaticky rozpoznáva slabé kategórie na základe historickej úspešnosti študenta.
    - Ak kategória má pod 50 % úspešnosť, tutor dostáva vyššiu odmenu za jej zlepšenie.
    - Penalizácia je vyššia pri stagnácii alebo zhoršení.
    """
    def __init__(self):
        self.category_performance = {}  

    def update_performance(self, category, correct):
        """Aktualizuje úspešnosť pre kategóriu."""
        if category not in self.category_performance:
            self.category_performance[category] = {"correct": 0, "incorrect": 0}

        if correct:
            self.category_performance[category]["correct"] += 1
        else:
            self.category_performance[category]["incorrect"] += 1

    def is_weak_category(self, category):
        """Dynamicky určuje, či je kategória slabá (pod 60 % úspešnosť)."""
        stats = self.category_performance.get(category, {"correct": 0, "incorrect": 0})
        total_attempts = stats["correct"] + stats["incorrect"]

        if total_attempts == 0:
            return False  # Ak nemáme údaje, neoznačujeme kategóriu ako slabú

        accuracy = stats["correct"] / total_attempts
        return accuracy < 0.6  # Ak úspešnosť klesne pod 60 %, kategória sa považuje za slabú

    def reward(self, state, action, next_state):
        """Priradí odmenu na základe vývoja znalostí a dynamického určenia slabých kategórií."""
        weak = self.is_weak_category(action.category)

        if next_state.knowledge_level > state.knowledge_level:
            return 15 if weak else 10  # Vyššia odmena za slabé kategórie
        elif next_state.knowledge_level == state.knowledge_level:
            return -1  
        else:
            return -5 if weak else -10

class TutorPolicyModel(pomdp_py.PolicyModel):
    """
    Tutor sa dynamicky prispôsobuje vedomostiam študenta:
    
    1 Preferuje kategórie s nižšou úspešnosťou, ale neoznačuje ich priamo ako "slabé"
    2️ Ak študent odpovie 3+ krát zle, vyberie najsilnejšiu kategóriu
    3️ Používa ε-greedy prístup, aby nevzniklo jednostranné učenie
    """
    
    def __init__(self, categories, epsilon=0.15):
        self.categories = categories
        self.category_performance = {category: {"correct": 0, "incorrect": 0, "streak": 0} for category in categories} 
        self.epsilon = epsilon  

    def update_performance(self, category, correct):
        """Aktualizuje štatistiky študenta na základe odpovede."""
        if correct:
            self.category_performance[category]["correct"] += 1
            self.category_performance[category]["streak"] = 0  
        else:
            self.category_performance[category]["incorrect"] += 1
            self.category_performance[category]["streak"] += 1  

    def sample(self, state):
        """Vyberie kategóriu otázky podľa dynamickej stratégie."""
        category_scores = {}

        for category, stats in self.category_performance.items():
            total = stats["correct"] + stats["incorrect"]
            if total == 0:
                accuracy = 0
                category_scores[category] = 1  
            else:
                accuracy = stats["correct"] / total
                category_scores[category] = 1 - accuracy  

        # Ak má kategória 3+ nesprávne odpovede za sebou, prepneme na silnú kategóriu
        for category, stats in self.category_performance.items():
            if stats["streak"] >= 3:
                print(f"Tutor identifikoval 3 nesprávne odpovede v kategórii {category} → Switching to strong category!")
                self.category_performance[category]["streak"] = 0  
                return self._choose_strongest_category()

        # ε-greedy výber: občas vyberieme náhodne, inak preferujeme kategórie s nižšou úspešnosťou
        if random.random() < self.epsilon:
            chosen_category = random.choice(self.categories)  
        else:
            chosen_category = max(category_scores, key=category_scores.get)  

        return TutorAction(chosen_category)

    def _choose_strongest_category(self):
        """Vyberie náhodnú kategóriu z tých, ktoré nie sú slabé."""
        weak_categories = set()
        for category, stats in self.category_performance.items():
            total_attempts = stats["correct"] + stats["incorrect"]
            if total_attempts > 0:
                accuracy = stats["correct"] / total_attempts
                if accuracy < 0.6:
                    weak_categories.add(category)
        
        strong_categories = [cat for cat in self.categories if cat not in weak_categories]
        
        if not strong_categories:
            return TutorAction(random.choice(self.categories))
        
        return TutorAction(random.choice(strong_categories))


class TutorPOMDP(pomdp_py.POMDP):
    def __init__(self, categories):
        self.categories = categories
        init_category = random.choice(categories)
        init_level = 1
        init_state = TutorState(init_category, init_level)

        agent = pomdp_py.Agent(
            pomdp_py.Histogram({init_state: 1.0}), 
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
        self.env.reward_model.update_performance(category, correct)
        self.agent.policy_model.update_performance(category, correct)

        return observation, reward