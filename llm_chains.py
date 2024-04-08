import json
from typing import List
from secret import OPEN_AI_KEY
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from task_template import TaskTemplate

llm = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0.7, openai_api_key=OPEN_AI_KEY, streaming=False)
llm4 = ChatOpenAI(model="gpt-4", temperature=0.7, openai_api_key=OPEN_AI_KEY, streaming=False)

def create_task_generation_chain(task_template: TaskTemplate): 
    # create pydantic class 
    pydantic_class = task_template.generate_dynamic_class()
    # define json parser 
    output_json_parser = JsonOutputParser(pydantic_object=pydantic_class)

    task_generation_prompt = PromptTemplate(
        template="""
            You are a part of a program that helps with language learning.
            You will be assisting in creating high quality exercises for learners.
            Exercises are created from tasks that are described in a task template
            that also contains information on the parameters that go into that tempalte.
            Exercise help learners to learn words listed in "target words".
            Your tasks is to complete the template by providing the values for the parameters.
            The values for the parameters are called resources and they are given in the target
            language.
            
            You role is to create these exercises with the provided template. The learners will then
            solve the exerices you created.

            {format_instructions}

            Perform the task for the following:
            template: {template}
            parameter description: {parameter_description}
            target words: {target_words}
            """,
            input_variables=["target_words"],
            partial_variables={
                "format_instructions": output_json_parser.get_format_instructions(),
                "template": task_template.template.template,
                "parameter_description": json.dumps(task_template.parameter_description)
            }
    )

    chain = task_generation_prompt | llm4 | output_json_parser
    return chain

"""
            Example: the template may say "From all the words below complete the blank in the sentence:
            $sentence. 1) $option1 2) $option2 3) $option3 4) option4." 
            Parameter description may be : 'sentence' - sentence with a blank to be completed , 'option1'
            first option for completion task, 'option2' second option, 'option3' third option, 'option4' fourth option.
            The target words may be:  
            ["erklären"]. 

            Your task in this case would be to provide something like 
            'sentence': "Die Regierung hat neue Richtlinien eingeführt, um die gefährdeten Arten in ihrem natürlichen Lebensraum zu _______."
                'option1': erklären 
                'option2': schützen 
                'option3': verbessern
                'option4': beobachten
"""
