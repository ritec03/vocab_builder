from abc import ABC, abstractmethod
from typing import List, Set, Dict
import copy
from data_structures import EXERCISE_THRESHOLD, LexicalItem, Score
from evaluation_method import AIEvaluation, EvaluationMethod
from task_template import Resource, TaskTemplate

# TODO write code for resource saving into database
# TODO create example templates manually

class Task(ABC):
    def __init__(
            self, 
            template: TaskTemplate, 
            resources: Dict[str, Resource], 
            learning_items: Set[LexicalItem],
            answer: str,
            task_id: int
        ):
        """
        Initialize a new task with a template and resources and evaluation method.
        
        :param template: tempalte compatible with this task type
        :param resources: A dictionary of resources with identifiers and resources to fill the template.
        :param learning_items: a set of words to be learned.
        """
        self.template = template
        if set(self.template.identifiers) != set(resources.keys()):
            raise ValueError("Template identifiers do not match resource keys")
        self.resources = resources
        self.learning_items = learning_items
        self.correctAnswer = answer  # This should be set by subclasses where the task is fully defined.
        self.evaluation_method = self.initialize_evaluation_method()
        self.id = task_id

    @abstractmethod
    def initialize_evaluation_method(self) -> EvaluationMethod:
        """
        Initialize evaluation method for this task type.
        """
        pass

    def produce_task(self) -> str:
        """
        Produces the task by combining the template with resources. This should be implemented by subclasses to
        fill the template with appropriate resources, creating a specific instance of the task.
        
        :return: The complete task as a string.
        """
        return self.template.substitute(self.resources)

    def evaluate_user_input(self, user_input: str) -> List[Score]:
        """
        :return: list of tuples of word id and score
        The list should be equal to the power of the learning_items set and should
        assign scores to all items in that set.
        """
        return self.evaluation_method.evaluate(self.correctAnswer, user_input, self.learning_items)
    
class OneWayTranslaitonTask(Task):
    """
    Defines a simple translation task that contains a task description,
    a single string to be translated from the target language into english.
    """
    def __init__(
            self, 
            template: TaskTemplate, 
            resources: Dict[str, Resource], 
            learning_items: Set[LexicalItem],
            answer: str,
            task_id: int
    ):
        super().__init__(template, resources, learning_items, answer, task_id)

    def initialize_evaluation_method(self) -> EvaluationMethod:
        return AIEvaluation({"task": self.produce_task()})
