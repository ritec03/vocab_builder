from abc import ABC, abstractmethod
from typing import List, Set, Dict, Tuple
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

class EvaluationMethod(ABC):
    """
    Class that defines an evaluation strategy
    It operates with gold standard answer, user answer and a context (such as task).
    Context is defined by a class that uses the evaluation (such as by a concrete task class).
    """
    def __init__(self, context: Dict[str, str]):
        self.context = context

    @abstractmethod
    def evaluate(self, gold_standard:str, user_answer: str, target_words: List[LexicalItem]):
        """
        Method that evaluates user answer against the gold standard with
        consideration of the context.
        """
        pass

class Task(ABC):
    def __init__(
            self, 
            template_name: str, 
            resources: Dict[str, Resource], 
            learning_items: Set[LexicalItem],
            asnwer: str
        ):
        """
        Initialize a new task with a template and resources and evaluation method.
        
        :param template_name: name of the tempalte compatible with this task type
        :param resources: A dictionary of resources with identifiers and resources to fill the template.
        :param learning_items: a set of words to be learned.
        """
        self.template = self.get_template(template_name)
        if set(self.template.identifiers) != set(resources.keys()):
            raise ValueError("Template identifiers do not match resource keys")
        self.resources = resources
        self.learning_items = learning_items
        self.correctAnswer = asnwer  # This should be set by subclasses where the task is fully defined.
        self.evaluation_method = self.initialize_evaluation_method()

    @abstractmethod
    def initialize_evaluation_method(self) -> EvaluationMethod:
        """
        Initialize evaluation method for this task type.
        """
        pass

    @abstractmethod
    def get_template(self, template_name: str) -> TaskTemplate:
        """
        Check that the template found at the template name is compatible with this
        task class and if so return task tempalte, if not, raise an error
        """
        raise NotImplementedError("Get template is not implemented.")

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

    def get_task_for_word(self, target_words: Set[str], criteria: List) -> Task:
        """
        Retrieves or generates tasks based on the target set of words and additional criteria.
        
        :param target_words: The set of target words for which to find or generate tasks.
        :param criteria: A list of criteria objects to apply in task selection.
        :return: A list of Task objects.
        """
        # tasks = db.fetch_tasks(criteria)
        tasks = [] # NOTE nothing for now
        if tasks:
            return tasks[0] # NOTE for now just return the first task
        else:
            return self.generate_task(target_words, criteria)

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

    @abstractmethod
    def fetch_or_generate_resources(
            self, 
            template: TaskTemplate, 
            target_words: Set[LexicalItem], 
            generate = False
        ) -> Tuple[Dict[str, Resource], str]:
        """
        Fetches or generates resources required by a task template, aiming to cover the target lexical items.
        Missing resources will be covered by generation or if generate flag is True, all resources will be generated.

        Args:
            template: The TaskTemplate object for which resources are required.
            target_words: A set of LexicalItem objects that the task aims to help the user learn.

        Returns:
            A dictionary mapping template parameter identifiers to Resource objects.
            An answer string for the task
        """
        pass

    def create_task(
            self, 
            target_words: Set[LexicalItem], 
            answer: str=None, 
            template: TaskTemplate=None, 
            resources: Dict[str, Resource]=None,
            generate=False
        ) -> Task:
        """
        Creates a Task object from the template, resources, and correct answer.

        Args:
            template: The TaskTemplate object used for the task.
            resources: A dictionary mapping identifiers to Resource objects.
            answer: A string representing the correct answer for the task.
            target_words: A set of LexicalItem objects that the task aims to help the user learn.
            generate: whether or not to generate the template and resources

        Returns:
            A Task object.
        """
        if not resources:
            resources, answer = self.fetch_or_generate_resources(template, target_words, generate)
        if not answer:
            raise Exception("Answer is not provided.")

        return Task(template, resources, target_words, answer)
        

class ManualTaskGenerator(TaskGenerator):
    pass

class AITaskGenerator(TaskGenerator):

    def fetch_or_generate_resources(
        self, 
        template: TaskTemplate, 
        target_words: Set[LexicalItem], 
        generate: bool = False
    ) -> Tuple[Dict[str, Resource], str]:
        """
        Fetches or generates resources required by a task template, aiming to cover the target lexical items.
        Missing resources will be covered by generation or if generate flag is True, all resources will be generated.
        """
        raise NotImplementedError("AI logic to fetch or generate resources needs implementation.")