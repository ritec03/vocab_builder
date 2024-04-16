from data_structures import TaskType
from database import DB
from task_template import TaskTemplate


class TemplateRetriever():    
    # TODO get template or generate it 
    def get_random_template_for_task_type(self, task_type):
        """provide a random template that adheres to the type"""
        if task_type == TaskType.ONE_WAY_TRANSLATION:
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
                    "sentence": "sentence in target language to be translated into english."
                },
                task_type=TaskType.ONE_WAY_TRANSLATION
            )
            try: 
                added_task_template = DB.add_template(
                    task_template.template.template,
                    task_template.description,
                    task_template.examples,
                    task_template.parameter_description,
                    task_template.task_type
                )
                return added_task_template
            except:
                return DB.get_template_by_id(1)
        else:
            raise ValueError("No such task type exists.")
    
    def get_template_by_name(self, template_name):
        pass