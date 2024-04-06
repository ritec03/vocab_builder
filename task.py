from abc import ABC, abstractmethod
from typing import List, Set, Dict
import copy
from data_structures import LexicalItem, Score
from string import Template
from dataclasses import dataclass

# from database import DatabaseManager

@dataclass
class Resource():
    resource_id: int
    resource_string: str

class TaskTemplate():
    def __init__(
            self,
            template_id: int, 
            template_string: str, 
            template_description: str,
            tempplate_examples: List[str],
            parameter_description: Dict[str, str]
        ):
        """
        template id should be a valid int
        template string should be a non-empty string
        description should be a non-empty string
        examples should have at least one string entry
        parameter description should have correct argument number
            and should describe the parameters that go into the template
        """
        if not isinstance(template_id, int):
            raise ValueError("Passed id that is not an integer")
        elif not template_string or not isinstance(template_string, str):
            raise ValueError("Template string s empty or not a string.")
        elif not template_description or not isinstance(template_description, str):
            raise ValueError("Template description is empty or not a string.")
        elif not isinstance(tempplate_examples, List) or not tempplate_examples:
            raise ValueError("Template examples is empty list or not a list.")

        self.id = template_id
        self.template = Template(template_string)
        self.description = template_description
        self.examples = tempplate_examples
        self.parameter_description = parameter_description

        try:
            self.template.substitute(self.parameter_description)
        except:
            raise ValueError("Parameter description contains wrong parameter number.")

        # if not self.template.is_valid():
        #     raise ValueError("Template is not a valid template")
        self.identifiers = [key for key, value in self.parameter_description.items()]

    def substitute(self, resources: Dict[str, Resource]) -> str:
        """
        Produce filled template string using provided dictionary of resources.
        The produvided dictionary must be compatible with this template.
        """
        resource_strings = {key: resource.resource_string for key, resource in resources.items()}
        filled_template = self.template.substitute(resource_strings)
        return filled_template

class Task(ABC):
    def __init__(
            self, 
            template: TaskTemplate, 
            resources: Dict[str, Resource], 
            learning_items: Set[LexicalItem], 
            asnwer: str
        ):
        """
        Initialize a new task with a template and resources.
        
        :param template: A string template for the task, where placeholders are to be filled with resources.
        :param resources: A dictionary of resources with identifiers and resources to fill the template.
        :param learning_items: a set of words to be learned.
        """
        self.template = template
        if set(self.template.identifiers) != set(resources.keys()):
            raise ValueError("Template identifiers do not match resource keys")
        self.resources = resources
        self.learning_items = learning_items
        self.correctAnswer = asnwer  # This should be set by subclasses where the task is fully defined.


    def produce_task(self) -> str:
        """
        Produces the task by combining the template with resources. This should be implemented by subclasses to
        fill the template with appropriate resources, creating a specific instance of the task.
        
        :return: The complete task as a string.
        """
        return self.template.substitute(self.resources)

    @abstractmethod
    def evaluate_user_input(self, user_input: str) -> List[Score]:
        """
        :return: list of tuples of word id and score
        The list should be equal to the power of the learning_items set and should
        assign scores to all items in that set.
        """
        pass

    def get_evaluation(self, user_input: str, evaluation): # NOTE no type hint due to circular import of Evaluation
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

class TaskFactory:
    def __init__(self):
        pass

    def get_tasks_for_words(self, target_words: Set[str], criteria: List) -> List[Task]:
        """
        Retrieves or generates tasks based on the target set of words and additional criteria.
        
        :param target_words: The set of target words for which to find or generate tasks.
        :param criteria: A list of criteria objects to apply in task selection.
        :return: A list of Task objects.
        """
        # tasks = db.fetch_tasks(criteria)
        tasks = [] # NOTE for now
        if tasks:
            return tasks[0] # NOTE for now just return the first task
        else:
            return [self.generate_task(target_words, criteria)]

    def generate_task(self, target_words: Set[str], criteria: List) -> Task:
        """
        Generates a new task based on the target words and criteria.
        This method should be invoked when there are not tasks that
        satisfy the criteria in db.

        The method will generate task using various means.
        Generating a task will require choosing or creating template,
        satisfying criteria for task generation (ignore other criteria),
        choosing resources and saving the task.
        """
        raise NotImplementedError()
    

class TaskGenerator(ABC):
    """
    The abstract class defines a component responsible for generation of
    tasks based on criteria.
    """
    pass

class ManualTaskGenerator(TaskGenerator):
    pass

class AITaskGenerator(TaskGenerator):
    pass