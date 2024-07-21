from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Set, Dict, Type
import copy
from data_structures import EXERCISE_THRESHOLD, FourChoiceAnswer, LexicalItem, Score, TaskType
from evaluation_method import AIEvaluation, EvaluationMethod
from task_template import Resource, TaskTemplate
import logging

logger = logging.getLogger(__name__)

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
        self.correctAnswer = answer
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

    def evaluate_user_input(self, user_input: str) -> Set[Score]:
        """
        :return: list of tuples of word id and score
        The list should be equal to the power of the learning_items set and should
        assign scores to all items in that set.
        """
        return self.evaluation_method.evaluate(self.correctAnswer, user_input, self.learning_items)
    
    # TODO change to json methods to be more consistent
    def to_json(self):
        converted_resources = dict()
        for key in self.resources:
            converted_res = {
                "id": self.resources[key].resource_id,
                "resource": self.resources[key].resource,
                "target_words": [word.to_json() for word in self.resources[key].target_words]
            }
            converted_resources[key] = converted_res
        return {
            'task_string': self.produce_task(),
            'template': self.template.to_json(),  # Assuming template has to_json method
            'resources': converted_resources,
            'learning_items': [item.to_json() for item in self.learning_items],
            'correctAnswer': self.correctAnswer,
            'id': self.id
        }
    
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
        # validate that answer is a string.
        if not isinstance(answer, str):
            raise ValueError("Answer is not a string.")
        super().__init__(template, resources, learning_items, answer, task_id)

    def initialize_evaluation_method(self) -> EvaluationMethod:
        return AIEvaluation({"task": self.produce_task()})
    
    def evaluate_user_input(self, user_input: str) -> Set[Score]:
        if not isinstance(user_input, str):
            raise ValueError("User input is not a string.")
        return super().evaluate_user_input(user_input)

class FourChoiceTask(Task):
    # TODO define class methods for template validation
    """
    Defines a simple multiple-choice question task with four answer possibilities
    and one correct answer.
    """
    def __init__(
            self, 
            template: TaskTemplate, 
            resources: Dict[str, Resource], 
            learning_items: Set[LexicalItem], 
            answer: str, 
            task_id: int
        ):
        # validate that answer is one of four options a, b, c or d.
        logger.info(resources)
        logger.info("The answer is %s", answer)
        if answer not in [a.name for a in list(FourChoiceAnswer)]:
            raise ValueError("Answer is not one of the FourChoiceAnswer options.")

        # validate that resources contain 4 answer options A, B, C and D
        required_keys = {'A', 'B', 'C', 'D'}
        if not required_keys <= resources.keys():
            missing_keys = required_keys - resources.keys()
            raise ValueError(f"Resources missing for options: {', '.join(missing_keys)}")

        # Optional: Validate that each key maps to an instance of Resource
        for key in required_keys:
            if not isinstance(resources.get(key), Resource):
                raise ValueError(f"Resource for option {key} is not a valid Resource instance.")

        super().__init__(template, resources, learning_items, answer, task_id)

    def initialize_evaluation_method(self) -> EvaluationMethod:
        return AIEvaluation({"task": self.produce_task()})
    
    def evaluate_user_input(self, user_input: str) -> Set[Score]:
        if user_input not in [a.name for a in list(FourChoiceAnswer)]:
            raise ValueError("User input is not one of four options.")
        return super().evaluate_user_input(user_input)

    # TODO change to json methods to be more consistent
    def to_json(self):
        repr = super().to_json()
        repr["correctAnswer"] = self.correctAnswer
        return repr
    
def get_task_type_class(task_type: TaskType) -> Type[Task]:
    if task_type == TaskType.FOUR_CHOICE:
        return FourChoiceTask
    elif task_type == TaskType.ONE_WAY_TRANSLATION:
        return OneWayTranslaitonTask
    else:
        raise ValueError("Unknown task type ", task_type)
    
