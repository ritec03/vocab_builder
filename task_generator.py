import json
import logging
from data_structures import TASKS_FILE_DIRECTORY, LexicalItem, TaskType
from database_orm import DatabaseManager
from llm_chains import invoke_task_generation_chain
from task import Task
from task_template import Resource, TaskTemplate
from template_retriever import TemplateRetriever
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

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
        target_words: set[LexicalItem],
    ) -> tuple[dict[str, Resource], str]:
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
        target_words: set[LexicalItem],
        task_type: TaskType,
        template: TaskTemplate | None = None,
        answer: str | None = None,
        resources: dict[str, Resource] | None = None,
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
            template = TemplateRetriever(
                self.db_manager
            ).get_random_template_for_task_type(task_type)
        if not template.id:
            raise Exception(
                "Template does not have an id. Perhaps it's not been put into the database."
            )
        if not resources:
            resources, answer = self.fetch_or_generate_resources(template, target_words)
        if not answer:
            raise Exception("Answer is not provided.")

        task = self.db_manager.add_task(template.id, resources, target_words, answer)
        return task

    def check_resource_target_word_match(
        self, resource_dict: dict[str, Resource], target_words: set[LexicalItem]
    ) -> bool:
        # Minimal check that every item in target words appears in at least one resource.
        for word in target_words:
            found = any(
                word.id in list(map((lambda x: x.id), resource.target_words))
                for resource in resource_dict.values()
            )
            if not found:
                return False
        return True


class AITaskGenerator(TaskGenerator):
    def create_task(
        self,
        target_words: set[LexicalItem],
        task_type: TaskType,
        template: TaskTemplate | None = None,
        answer: str | None = None,
        resources: dict[str, Resource] | None = None,
    ) -> Task:
        """
        Additionally to creating a task, saves a serialized version
        of the task to file called tasks.json.
        """
        task = super().create_task(target_words, task_type, template, answer, resources)
        # TODO ignore IDs
        try:
            try:
                with open(TASKS_FILE_DIRECTORY, "r") as f:
                    existing_tasks = json.load(f)
            except Exception:
                existing_tasks = []

            existing_tasks.append(task.to_json())
            with open(TASKS_FILE_DIRECTORY, "w") as f:
                json.dump(existing_tasks, f, indent=4)
        except Exception as e:
            logger.warning("Failed to save generated tasks due to this error", e)

        return task

    def fetch_or_generate_resources(
        self,
        template: TaskTemplate,
        target_words: set[LexicalItem],
    ) -> tuple[dict[str, Resource], str]:
        """
        Fetches or generates resources required by a task template, aiming to cover the target lexical items.

        Pass target words, template and parameter description to AI.
        """
        output_dict = invoke_task_generation_chain(target_words, template)
        logger.info(output_dict)
        # Check that output contains all keys of template.parameter_description. Raise exception otherwise
        if not set(template.parameter_description.keys()).issubset(output_dict.keys()):
            raise ValueError(
                "Output does not contain all keys of template.parameter_description"
            )

        # Separate answer key-value pair from output (and remove that key from output), then return tuple (Dict of parameter-resource, answer)
        answer = output_dict.pop("answer", None)

        if answer is None:
            raise ValueError("Answer is absent from the LLM output.")

        # Generate resource tuple
        # NOTE for now assuming every resource relates to every target word
        """
        # TODO
        Problem:
        Tasks like four choice task have resources that do not have any target words necessarily as three answers are
        usually wrong. So they can contain anything. What kind of resources should these be?
        * they can have resource of their own words -> but their target word then is not going to appear on task's
            target word which is good.
            * however, there can also be target words that do not appear in the task's target words just because those
            are not primary target words but still can be studied... but i guess wrong choices in multiple choice
            are also kind of practice?

        Solution for now -> create resources that just contain words for themselves???
            * but this would require finding those generated words in the database -> so need functionality for that too.
        Perhaps, to be solved slightly later.
        """
        resource_dict = {
            param: self.db_manager.add_resource_manual(value, target_words)
            for param, value in output_dict.items()
        }
        if not self.check_resource_target_word_match(resource_dict, target_words):
            raise ValueError(
                "Some target words are not covered by any generated resource."
            )

        return resource_dict, answer
