from abc import ABC, abstractmethod
import json
import random
from typing import Dict, List, Set, Tuple
from data_structures import LexicalItem, TaskType
from database_orm import DatabaseManager
from llm_chains import invoke_task_generation_chain
from task import Task
from task_template import Resource, TaskTemplate
from template_retriever import TemplateRetriever
import logging

logger = logging.getLogger(__name__)

class TaskFactory:
    """Either retrieves or generates a task"""
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def get_task_for_word(self, target_words: Set[LexicalItem], template: TaskTemplate=None, criteria: List=[]) -> Task:
        """
        Retrieves or generates tasks based on the target set of words and additional criteria.
        
        :param target_words: The set of target words for which to find or generate tasks.
        :param criteria: A list of criteria objects to apply in task selection.
        :return: A list of Task objects.
        """
        # TODO implement retrieval of tasks based on criteria.
        tasks = self.db_manager.get_tasks_for_words(target_words, 10)
        if tasks:
            return random.choice(tasks) # NOTE for now just return a random task
        else:
            return self.generate_task(target_words, template, criteria)

    def generate_task(self, target_words: Set[LexicalItem], template: TaskTemplate=None, criteria: List=[]) -> Task:
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
        task_generator = AITaskGenerator(self.db_manager)
        task_type = random.choice(list(TaskType))
        task = task_generator.create_task(target_words, task_type, template=template)
        return task




class TaskGenerator(ABC):
    """
    The abstract class defines a component responsible for generation of
    tasks based on criteria.
    """
    # TODO think about what to do when only subset of resources in the database
    # - generate the rest?

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

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
            template: TaskTemplate=None,
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
        if not template:
            template = TemplateRetriever(self.db_manager).get_random_template_for_task_type(task_type)
        if not resources:
            resources, answer = self.fetch_or_generate_resources(template, target_words)
        if not answer:
            raise Exception("Answer is not provided.")

        task = self.db_manager.add_task(template.id, resources, target_words, answer)
        return task
        
    def check_resource_target_word_match(self, resource_dict: Dict[str, Resource], target_words: Set[LexicalItem]) -> bool:
        # Minimal check that every item in target words appears in at least one resource.
        for word in target_words:
            found = False
            for resource in resource_dict.values():
                if word.id in list(map((lambda x: x.id), resource.target_words)):
                    found = True
                    break
            if not found:
                return False
        return True

class ManualTaskGenerator(TaskGenerator):
    pass

class AITaskGenerator(TaskGenerator):
    def create_task(self, target_words: Set[LexicalItem], task_type: TaskType, template: TaskTemplate = None, answer: str = None, resources: Dict[str, Resource] = None) -> Task:
        """
        Additionally to creating a task, saves a serialized version
        of the task to file called tasks.json.
        """
        task = super().create_task(target_words, task_type, template, answer, resources)
        # TODO ignore IDs
        try:
            try:
                with open('tasks.json', 'r') as f:
                    existing_tasks = json.load(f)
            except:
                existing_tasks = []

            existing_tasks.append(task.to_json())
            with open('tasks.json', 'w') as f:
                json.dump(existing_tasks, f, indent=4)
        except Exception as e:
            logger.warning("Failed to save generated tasks due to this error", e)

        return task

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
        logger.info(output_dict)
        # Check that output contains all keys of template.parameter_description. Raise exception otherwise
        if not set(template.parameter_description.keys()).issubset(output_dict.keys()):
            raise ValueError("Output does not contain all keys of template.parameter_description")
        
        # Separate answer key-value pair from output (and remove that key from output), then return tuple (Dict of parameter-resource, answer)
        answer = output_dict.pop('answer', None)

        if answer == None:
            raise ValueError("Answer is absent from the LLM output.")
    
        # Generate resource tuple
        # NOTE for now assuming every resource relates to every target word
        resource_dict = {param: self.db_manager.add_resource_manual(value, target_words) for param, value in output_dict.items()}
        if not self.check_resource_target_word_match(resource_dict, target_words):
            raise ValueError(f"Some target words are not covered by any generated resource.")

        return resource_dict, answer