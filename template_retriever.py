from data_structures import TaskType
from task_template import TaskTemplate
import random  # Import for random selection
from database_orm import DB

class TemplateRetriever():
    def get_random_template_for_task_type(self, task_type: TaskType) -> TaskTemplate:
        """
        Provide a random template that adheres to the specified task type.

        Args:
            task_type (TaskType): The task type for which to retrieve a template.

        Returns:
            TaskTemplate: A randomly selected template of the given task type.

        Raises:
            ValueError: If no templates are found for the task type.
        """
        if not isinstance(task_type, TaskType):
            raise ValueError("No such task type exists.")
        
        templates = DB.get_templates_by_task_type(task_type)  # Retrieve templates by task type

        if not templates:
            raise ValueError("No templates available for the given task type. ", task_type.name)

        return random.choice(templates)  # Randomly select and return one template from the list

    
    def get_template_by_name(self, template_name):
        pass