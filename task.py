from abc import ABC, abstractmethod
import random
from typing import List, Set, Dict, Tuple
import copy
from data_structures import MAX_SCORE, MIN_SCORE, LexicalItem, Score, TaskType
from llm_chains import DynamicAIEvaluation, create_task_generation_chain, invoke_evaluation_chain, invoke_task_generation_chain
from task_template import Resource, TaskTemplate, TemplateRetriever

# TODO add diversification into gpt prompts
# TODO write code for resource saving into database
# TODO create example templates manually

class EvaluationMethod(ABC):
    """
    Class that defines an evaluation strategy
    It operates with gold standard answer, user answer and a context (such as task).
    Context is defined by a class that uses the evaluation (such as by a concrete task class).
    """
    def __init__(self, context: Dict[str, str] = None):
        self.context = context

    @abstractmethod
    def evaluate(self, gold_standard:str, user_answer: str, target_words: Set[LexicalItem]) -> List[Score]:
        """
        Method that evaluates user answer against the gold standard with
        consideration of the context.
        """
        pass

# TODO create LLM-based evaluation.
class ExactMatchingEvaluation(EvaluationMethod):
    """
    Evaluation method for exact string matching.
    Case insensitive.
    """
    def evaluate(self, gold_standard:str, user_answer: str, target_words: Set[LexicalItem]) -> List[Score]:
        """
        Evaluate user answer against gold standard using exact string matching.
        """
        if gold_standard.lower().strip() == user_answer.lower().strip():
            return [Score(word.id, MAX_SCORE) for word in target_words]
        else:
            return [Score(word.id, MIN_SCORE) for word in target_words]
        
class AIEvaluation(EvaluationMethod):
    """
    Context should contain "task" field with stringified task.
    """
    def __init__(self, context: Dict[str, str]):
        self.context = context

    def evaluate(self, gold_standard:str, user_answer: str, target_words: Set[LexicalItem]) -> List[Score]:
        """
        Evaluation method that uses LLM-based evaluation of human input
        against the gold standard and context of the task.
        """
        # invoke evaluation chain.
        output = invoke_evaluation_chain(self.context["task"], gold_standard, user_answer, target_words)
        print(output)
        # Check that output is a dictionary that contains all words from target words as keys and
        # that all values are integers.
        if not isinstance(output, dict):
            raise ValueError("Output is not a dictionary")
        
        for word in target_words:
            if word.item not in output: # TODO update data structure
                raise ValueError(f"Output does not contain score for word: {word.item}")
            if not isinstance(output[word.item], int):
                raise ValueError(f"Score for word {word.item} is not an integer")
        
        # Convert the output into the final output form of List[Score]
        scores = [Score(word_id=word.id, score=output[word.item]) for word in target_words]
        return scores


class Task(ABC):
    def __init__(
            self, 
            template_name: str, 
            resources: Dict[str, Resource], 
            learning_items: Set[LexicalItem],
            answer: str
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
        self.correctAnswer = answer  # This should be set by subclasses where the task is fully defined.
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
        evaluation_result = self.evaluate_user_input(user_input)
        new_evaluation = copy.deepcopy(evaluation)
        new_evaluation.add_entry(self, user_input, evaluation_result)
        return new_evaluation
    
class OneWayTranslaitonTask(Task):
    """
    Defines a simple translation task that contains a task description,
    a single string to be translated from the target language into english.
    """
    def __init__(
            self, 
            template_name: str, 
            resources: Dict[str, Resource], 
            learning_items: Set[LexicalItem],
            answer: str      
    ):
        super().__init__(template_name, resources, learning_items, answer)

    def initialize_evaluation_method(self) -> EvaluationMethod:
        return AIEvaluation({"task": self.produce_task()})

    def get_template(self, template_name: str) -> TaskTemplate:
        """
        Dummy implementation for now
        """
        template_string = (
            "Translate the following into English:\n" +
            "   '$sentence'"
        )
        task_template = TaskTemplate(
            template_id=1,
            template_string=template_string,
            template_description="description",
            template_examples=["example one", "example two"],
            parameter_description={
                "sentence": "sentence in target langauge to be translated into english."
            }
        )
        return task_template

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
    """Either retrieves or generates a task"""
    def __init__(self):
        pass

    def get_task_for_word(self, target_words: Set[LexicalItem], criteria: List=[]) -> Task:
        """
        Retrieves or generates tasks based on the target set of words and additional criteria.
        
        :param target_words: The set of target words for which to find or generate tasks.
        :param criteria: A list of criteria objects to apply in task selection.
        :return: A list of Task objects.
        """
        # tasks = db.fetch_tasks(criteria)
        tasks = [] # NOTE task fetching from db is not implemented yet
        if tasks:
            return tasks[0] # NOTE for now just return the first task
        else:
            return self.generate_task(target_words, criteria)

    def generate_task(self, target_words: Set[LexicalItem], criteria: List=[]) -> Task:
        """
        Generates a new task based on the target words and criteria.
        This method should be invoked when there are not tasks that
        satisfy the criteria in db.

        The method will generate task using various means.
        Generating a task will require choosing or creating template,
        satisfying criteria for task generation (ignore other criteria),
        choosing resources and saving the task.
        """
        # NOTE choose task type at random for now and only use AI
        task_generator = AITaskGenerator()
        task_type = random.choice(list(TaskType))
        task = task_generator.create_task(target_words, task_type)
        return task


class TaskGenerator(ABC):
    """
    The abstract class defines a component responsible for generation of
    tasks based on criteria.
    """
    # TODO think about what to do when only subset of resources in the database
    # - generate the rest?

    @abstractmethod
    def fetch_or_generate_resources(
            self, 
            template: TaskTemplate, 
            target_words: Set[LexicalItem], 
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
            task_type: TaskType,
            answer: str=None, 
            resources: Dict[str, Resource]=None,
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
        # TODO think about logic for choosing templates
        template = TemplateRetriever().get_random_template(task_type)
        if not resources:
            resources, answer = self.fetch_or_generate_resources(template, target_words)
        if not answer:
            raise Exception("Answer is not provided.")

        if task_type == TaskType.ONE_WAY_TRANSLATION:
            return OneWayTranslaitonTask(template, resources, target_words, answer)
        else:
            raise Exception("Unsupported task type.")
        

class ManualTaskGenerator(TaskGenerator):
    pass

class AITaskGenerator(TaskGenerator):
    def fetch_or_generate_resources(
        self, 
        template: TaskTemplate, 
        target_words: Set[LexicalItem], 
    ) -> Tuple[Dict[str, Resource], str]:
        """
        Fetches or generates resources required by a task template, aiming to cover the target lexical items.

        Pass target words, template and parameter description to AI.
        """
        output_dict = invoke_task_generation_chain(target_words, template)
        print(output_dict)
        # Check that output contains all keys of template.parameter_description. Raise exception otherwise
        if not set(template.parameter_description.keys()).issubset(output_dict.keys()):
            raise ValueError("Output does not contain all keys of template.parameter_description")
        
        # Separate answer key-value pair from output (and remove that key from output), then return tuple (Dict of parameter-resource, answer)
        answer = output_dict.pop('answer', None)

        if answer == None:
            raise ValueError("Answer is absent from the LLM output.")

        # Generate resource tuple
        resource_dict = {param: Resource(resource_id=None, resource_string=value) for param, value in output_dict.items()}
        return resource_dict, answer