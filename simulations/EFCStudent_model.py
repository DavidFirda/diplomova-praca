import random
from collections import deque
import numpy as np
import matplotlib.pyplot as plt

class StudentMemory:
    def __init__(self, categories, weak_category, n=5):
        """
        Inicializácia pamäte študenta.
        :param categories: Zoznam kategórií otázok
        :param weak_category: Zoznam kategórií, v ktorých je študent slabý
        :param n: Počet posledných odpovedí, ktoré sa berú do úvahy
        """
        self.categories = categories
        self.weak_category = weak_category
        self.memory = {category: Record(category, n=n, weak_category=weak_category) for category in categories}
        self.probability_log = {category: [] for category in categories} 
    
    def answer_question(self, category):
        """
        Simuluje odpoveď študenta na otázku v danej kategórii.
        :param category: Kategória otázky
        :return: True, ak odpoveď bola správna, inak False
        """
        record = self.memory[category]
        recall_likelihood = record.get_recall_likelihood()
        
        #print(f"[DEBUG] Kategória: {category}, Pravdepodobnosť: {recall_likelihood:.6f}")
        
        success = random.random() < recall_likelihood
        record.update(success)
        
        #if not success:
        #    print(f"[WARNING] Nesprávna odpoveď pre {category} s pravdepodobnosťou {recall_likelihood:.6f}")
        #else: 
        #    print(f"Správna odpoveď pre {category} s pravdepodobnosťou {recall_likelihood:.6f}")    
        
        self.probability_log[category].append(recall_likelihood)
        
        return success
    
    def plot_probabilities(self):
        plt.figure(figsize=(10, 5))
        num_categories = len(self.probability_log)
        colormap = plt.get_cmap("nipy_spectral")
        colors = [colormap(i / num_categories) for i in range(num_categories)]  

        for idx, (category, values) in enumerate(self.probability_log.items()):
            plt.plot(values, label=category, color=colors[idx]) 

        plt.xlabel("Otázka č.")
        plt.ylabel("Pravdepodobnosť správnej odpovede")
        plt.title("Vývoj pravdepodobnosti správnych odpovedí počas učenia")
        plt.legend()
        plt.show()

class Record:
    def __init__(self, category, n=5, weak_category=None):
        """
        Trieda reprezentujúca pamäť študenta pre jednu kategóriu otázok.
        :param category: Kategória otázky
        :param n: Počet posledných odpovedí, ktoré sa berú do úvahy
        :param weak_category: Kategórie, v ktorých má študent nižšiu základnú pravdepodobnosť
        """
        self.category = category
        self.weak_category = weak_category
        self.no_attempts = 0
        self.correct_recalls = 0
        self.incorrect_recalls = 0
        self.leitner = 1 # Leitnerova úroveň 
        self.last_n = deque(maxlen=n) # FIFO buffer na posledných n odpovedí
        self.decay = 0.9
        self.weights = [self.decay ** i for i in range(n)]  # Váhovanie minulých odpovedí
        self.weights.reverse()

    def update(self, success):
        """
        Aktualizuje stav pamäte na základe novej odpovede.
        :param success: True, ak odpoveď bola správna, inak False
        """
        self.no_attempts += 1
        self.last_n.append(success) # Pridanie odpovede do histórie
        if success:
            self.correct_recalls += 1
            self.leitner += 2
        else:
            self.incorrect_recalls += 1
            # Ak študent odpovie nesprávne dvakrát za sebou, penalizujeme viac
            if len(self.last_n) >= 2 and all(not x for x in self.last_n):
                self.leitner = max(1, self.leitner // 3) 
            else:
                self.leitner = max(1, self.leitner // 2)

    def get_recall_likelihood(self):
        """
        Vypočíta pravdepodobnosť správnej odpovede na základe histórie.
        """
        if self.no_attempts == 0 or len(self.last_n) == 0:
            base_likelihood = 0.2 if self.category in self.weak_category else 0.95 
        else:
            try:
                weighted_sum = np.dot(self.last_n, self.weights[-len(self.last_n):]) 
                base_likelihood = weighted_sum / sum(self.weights)
            except ValueError:
                base_likelihood = 0.2 if self.category in self.weak_category else 0.95

        if len(self.last_n) > 0: 
            error_rate = sum(1 for x in self.last_n if not x) / len(self.last_n)
            base_likelihood *= (1 - 0.5 * error_rate)  
        
        if self.category not in self.weak_category:
            base_likelihood = 0.95  

        base_likelihood = min(1.0, base_likelihood + (self.leitner * 0.1))  
        return max(0.1, min(base_likelihood, 1.0))
