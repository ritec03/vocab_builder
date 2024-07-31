import random
from query_builder import QueryCriteria
from task_generator import AITaskGenerator
from data_structures import LexicalItem, TaskType
from database_orm import DatabaseManager
from task import Task
from task_template import TaskTemplate
import logging

logger = logging.getLogger(__name__)
"""
TODO
Add conditions on task choice:
- task has not been done by user
- task has not been done in some amount of time
- task was previously completed above some threshold or below some threshold
- task needs to be of a certain type
- task needs to have certain resources
- task needs to have certain target words

How to implement this?
"""

"""
Pydantic class for task factory options that contains the following:
- target words
- doneByUser: bool
- doneInTimePeriod: datetime delta - within time period (now - delta, now)
- doneEarlierThan: datetime delta - before this time period (now - delta)
- minScore: int
- maxScore: int
- taskType: TaskType
- resources: List[Resource]
using sqlalchemy version 2.0 (latest), how can I programmatically create a set of functions that modify a statement? Use case - I want to create a function that executes things based on a set of criteria, and each criteria may or may not add additional statements to the query. 
"""

class TaskFactory:
    """Either retrieves or generates a task"""

    def __init__(self, db_manager: DatabaseManager, user_id: int):
        self.db_manager = db_manager
        self.user_id = user_id

    def get_task_for_word(
        self,
        criteria: QueryCriteria,
        template: TaskTemplate | None = None,
    ) -> Task:
        """
        Retrieves or generates tasks based on the target set of words and additional criteria.

        :param target_words: The set of target words for which to find or generate tasks.
        :param criteria: A list of criteria objects to apply in task selection.
        :return: A list of Task objects.
        """
        if tasks := self.db_manager.get_tasks_by_criteria(self.user_id, criteria, 10):
            return random.choice(tasks)  # NOTE for now just return a random task
        elif criteria.target_words is not None:
            return self.generate_task(criteria.target_words, template)
        else:
            raise ValueError("No tasks found and no target words provided.")

    def generate_task(
        self,
        target_words: set[LexicalItem],
        template: TaskTemplate | None = None
    ) -> Task:
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
