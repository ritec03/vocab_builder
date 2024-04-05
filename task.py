from abc import ABC, abstractmethod
from typing import List, Set, Tuple
import copy
from data_structures import LexicalItem, Score


class Task(ABC):
    def __init__(self, template: str, resources: List[str], learning_items: Set[LexicalItem]):
        """
        Initialize a new task with a template and resources.
        
        :param template: A string template for the task, where placeholders are to be filled with resources.
        :param resources: A dictionary of resources (e.g., words, sentences) to fill in the template.
        :param learning_items: a set of words to be learned
        """
        self.template = template
        self.resources = resources
        self.learning_items = learning_items
        self.correctAnswer = None  # This should be set by subclasses where the task is fully defined.

    @abstractmethod
    def produce_task(self) -> str:
        """
        Produces the task by combining the template with resources. This should be implemented by subclasses to
        fill the template with appropriate resources, creating a specific instance of the task.
        
        :return: The complete task as a string.
        """
        pass

    @abstractmethod
    def evaluate_user_input(self, user_input) -> List[Score]:
        """
        :return: list of tuples of word id and score
        """
        pass

    def get_evaluation(self, user_input: str, evaluation): # NOTE no type hint due to circular import 
        """
        Evaluates the user's input against the correct answer and 
        creates a new evaluation manager object with the latest evaluation added to it.
        
        :param user_input: The user's input as a response to the task.
        :param evaluation: The EvaluationManager instance tracking the session's evaluation history.
        :return: The evaluation result as a new and updated object.
        """
        evaluation_result = self.evaluate_user_input()
        new_evaluation = copy.deepcopy(evaluation)
        new_evaluation.add_entry(self, user_input, evaluation_result)
        return new_evaluation

class HistoryEntry:
    def __init__(self, task: Task, response: str, evaluation_result: List[Score], correction=None):
        # evaluation result is a list of tuples of word_id and score (multiple words can be evaluated
        # in one evaluation)
        self.task = task
        self.response = response
        self.evaluation_result = evaluation_result
        self.correction = correction

class Evaluation:
    def __init__(self):
        self.history = []

    def add_entry(self, task: Task, response: str, evaluation_result: List[Score], correction=None):
        entry = HistoryEntry(task, response, evaluation_result, correction)
        self.history.append(entry)

    def get_history(self):
        return self.history
    
    def get_final_score(self) -> List[Score]:
        """
        Returns final score for the evaluation,
        which is the evaluation result of the last history entry

        :return: List[Score] a list of tuple of (word_id, score)
        """
        raise NotImplementedError()
    
    def to_json(self):
        return {
            "history": [entry.__dict__ for entry in self.history]
        }
