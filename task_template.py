from typing import List, Dict, Optional
from langchain_core.pydantic_v1 import BaseModel, Field, validator
from string import Template
from dataclasses import dataclass
from data_structures import Resource, TaskType, Language

class TaskTemplate():
    def __init__(
            self,
            target_language: Language,
            starting_language: Language,
            template_string: str,
            template_description: str,
            template_examples: List[str],
            parameter_description: Dict[str, str],
            task_type: TaskType,
            template_id: Optional[int] = None,
        ):
        """
        template id should be a valid int
        template string should be a non-empty string
        description should be a non-empty string
        examples should have at least one string entry
        parameter description should have correct argument number
            and should describe the parameters that go into the template
        """
        if not template_id:
            self.new = True
        elif not isinstance(template_id, int):
            raise ValueError("Passed id that is not an integer")
        elif not template_string or not isinstance(template_string, str):
            raise ValueError("Template string s empty or not a string.")
        elif not template_description or not isinstance(template_description, str):
            raise ValueError("Template description is empty or not a string.")
        elif not isinstance(template_examples, List) or not template_examples:
            raise ValueError("Template examples is empty list or not a list.")
        elif not isinstance(task_type, TaskType):
            raise ValueError("Unknown task type.")
        elif not isinstance(target_language, Language):
            raise ValueError("Unknown target langauge")
        elif not isinstance(starting_language, Language):
            raise ValueError("Unknown starting langauge")

        self.id = template_id
        self.template = Template(template_string)
        self.description = template_description
        self.examples = template_examples
        self.parameter_description = parameter_description
        self.task_type = task_type
        self.starting_language = starting_language
        self.target_language = target_language

        try:
            self.template.substitute(self.parameter_description)
        except:
            raise ValueError("Parameter description contains wrong parameter number.")

        # if not self.template.is_valid():
        #     raise ValueError("Template is not a valid template")
        self.identifiers = [key for key, value in self.parameter_description.items()]

    def set_id(self, id: int):
        if self.new:
            self.id = id
            self.new = False
        else:
            raise ValueError("The id has already been set.")

    def substitute(self, resources: Dict[str, Resource]) -> str:
        """
        Produce filled template string using provided dictionary of resources.
        The produvided dictionary must be compatible with this template.
        """
        resource_strings = {key: resource.resource for key, resource in resources.items()}
        filled_template = self.template.substitute(resource_strings)
        return filled_template
    
    def substitute_dummy(self) -> str:
        """
        Substitutes all parameters in the string with [PLACEHOLDER] string
        instead of actual resources.
        """
        dummy_resource_strings = {param: '[PLACEHOLDER]' for param in self.parameter_description}
        filled_template = self.template.substitute(dummy_resource_strings)
        return filled_template
    
    def generate_dynamic_class(self) -> type:
        """
        Generate a dynamic Pydantic model class based on the parameter description dictionary.
        
        Args:
            parameter_description: A dictionary mapping parameter names to their descriptions.
            
        Returns:
            A dynamically generated Pydantic model class with dummy validators for each field.
        """
        # Define a dictionary to hold the class attributes, including annotations
        attributes = {'__annotations__': {}}

        # Iterate over the parameter description dictionary
        for param_name, param_description in self.parameter_description.items():
            # Add each parameter as a class attribute with a Field description
            attributes[param_name] = Field(description=param_description)
            attributes['__annotations__'][param_name] = str # Assuming all fields are of type str for simplicity

            # Define a dummy validator function
            def make_validator(name):
                def dummy_validator(cls, value):
                    return value  # Just return the field value
                dummy_validator.__name__ = f'validate_{name}'  # Dynamically name the function based on the field name
                return dummy_validator

            # Add the dummy validator to the class attributes
            validator_name = f'validate_{param_name}'
            attributes[validator_name] = validator(param_name, allow_reuse=True)(make_validator(param_name))

        # Add a special 'answer' field
        attributes['answer'] = Field(description="The correct answer to the task. Eg. if it is translation, provide correct translation, if it's multiple choice, provide correct option, and so on.")
        attributes['__annotations__']['answer'] = str  # Assuming 'answer' is also of type str

        # Use type() to dynamically create the class with the specified attributes
        dynamic_class = type('DynamicTemplateParameters', (BaseModel,), attributes)

        return dynamic_class
    
