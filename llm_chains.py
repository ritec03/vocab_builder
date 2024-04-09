import json
from typing import List
from secret import OPEN_AI_KEY
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.output_parsers.fix import OutputFixingParser
from task_template import TaskTemplate
# import langchain

# langchain.debug = True

llm = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0.7, openai_api_key=OPEN_AI_KEY, streaming=False)
llm4 = ChatOpenAI(model="gpt-4", temperature=0.7, openai_api_key=OPEN_AI_KEY, streaming=False)

def create_task_generation_chain(task_template: TaskTemplate): 
    # create pydantic class 
    pydantic_class = task_template.generate_dynamic_class()
    # define json parser 
    output_json_parser = JsonOutputParser(pydantic_object=pydantic_class)

    # TODO Create a template such that all words can be processed at once.
    # could possibly require a better output fixing behaviour.
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
            solve the exerices you created. The target language is GERMAN. Do not provide resources
            in other languages.

            Do not say anything else, just return the well-formatted JSON string.

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
    return chain, output_json_parser

def invoke_chain(target_word: str, task_template: TaskTemplate):
    chain, output_parser = create_task_generation_chain(task_template)
    fix_parser = OutputFixingParser.from_llm(parser=output_parser, llm=llm4)
    try:
        output = chain.invoke({"target_words":target_word})
    except:
        try:
            fix_parser(output)
        except:
            raise Exception("Both parsers failed.")
        
    return output
