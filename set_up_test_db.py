import json
from typing import List, Dict, Tuple

import pandas as pd
from data_structures import TaskType, Language
from database import DB
from exercise import LessonGenerator
from task_template import TaskTemplate

# Assume TaskTemplate class is defined as provided earlier

def read_templates_from_json(file_path: str) -> List[TaskTemplate]:
    """
    Reads a JSON file and converts it into a list of TaskTemplate objects.
    
    Args:
        file_path (str): The path to the JSON file containing the templates.
        
    Returns:
        List[TaskTemplate]: A list of TaskTemplate objects.
    """
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    templates = []
    for item in data:
        try:
            template = TaskTemplate(
                template_id=item["template_id"],
                template_string=item["template_string"],
                template_description=item["template_description"],
                template_examples=item["template_examples"],
                parameter_description=item["parameter_description"],
                task_type=TaskType[item["task_type"]],
                starting_language=Language[item["starting_language"]],
                target_language=Language[item["target_language"]]
            )
            templates.append(template)
        except ValueError as e:
            print(f"Error processing item {item}: {e}")
    
    return templates

def write_template_json(template: TaskTemplate, file_path: str):
    """
    Writes a TaskTemplate object to a JSON file in a specific format.
    
    Args:
        template (TaskTemplate): The template to write.
        file_path (str): The path to the output JSON file.
    """
    template_dict = {
        "template_id": template.id,
        "template_string": template.template.template,
        "template_description": template.description,
        "template_examples": template.examples,
        "parameter_description": template.parameter_description,
        "task_type": template.task_type.name,  # Using the name of the enum for JSON compatibility
        "starting_language": template.starting_language.name,
        "target_language": template.target_language.name
    }
    
    with open(file_path, 'w') as file:
        json.dump(template_dict, file, indent=4)

# Example usage
if __name__ == "__main__":
    templates = read_templates_from_json("templates.json")
    
    DB.create_db()
    word_freq_output_file_path = "word_freq.txt"
    word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
    filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
    list_of_tuples: List[Tuple[str, str, int]] = list(filtered_dataframe.to_records(index=False))
    # convert numpy.int64 to Python integer
    list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples]
    DB.add_words_to_db(list_of_tuples)
    
    for template in templates:
        added_task_template = DB.add_template(
            template.template.template,
            template.description,
            template.examples,
            template.parameter_description,
            template.task_type,
            template.starting_language,
            template.target_language
        )
    
    # create user 
    user_id = DB.insert_user("test_user")
    print(user_id)
    user_id = 1

    lesson_generator = LessonGenerator(user_id ,DB)
    lesson = lesson_generator.generate_lesson()
    # create a test for lesson iteration
    lesson.perform_lesson()
    DB.close()


