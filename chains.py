import random
from helpers import choose_topic
from secret import OPEN_AI_KEY
from langchain.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_community.chat_models import ChatOpenAI

def choose_topic():
    topic_list = [
        "Daily routine and personal life",
        "Family and relationships",
        "Food and dining",
        "Shopping and bargaining",
        "Transportation and directions",
        "Weather and seasons",
        "Work and career",
        "Education and learning",
        "Technology and gadgets",
        " Arts and entertainment",
        " Music and dance",
        " Film and television",
        " Literature and poetry",
        " History and culture",
        " Holidays and traditions",
        " Sports and fitness",
        " Health and wellness",
        " Nature and environment",
        " Politics and current affairs",
        " Science and technology",
        " Business and economy",
        " Social media and communication",
        " Fashion and style",
        " Travel and tourism",
        " Personal development and goal-setting",
    ]
    return random.choice(topic_list)

llm = ChatOpenAI(openai_api_key=OPEN_AI_KEY)
str_output_parser = StrOutputParser()

PART_OF_SPEECH_LIST = ["noun", "verb", "adjective", "adverb", "conjunction", "preposition"]
def generate_parts_of_speech_string():
    # Adjusted weights for "conjunction" and "preposition"
    weights = [1, 1, 1, 1, 0.25, 0.25]
    
    # Generate a list of ten parts of speech using random.choices()
    selected_parts = random.choices(PART_OF_SPEECH_LIST, weights=weights, k=10)
    
    # Join the selected parts with commas and return as a single string
    result_string = ', '.join(selected_parts)
    
    return result_string

class WordList(BaseModel):
    words: list[str] = Field(description="list of words in the target language")
    target_language: str = Field(description="the target language")

word_list_json_parser = JsonOutputParser(pydantic_object=WordList)
topic_list = choose_topic() + "," +  choose_topic() + "," +  choose_topic()
print(topic_list)
pos_list = generate_parts_of_speech_string()
print(pos_list)
word_list_gen_prompt = PromptTemplate(
        template="""
        Create a list of ten words in the target language.
        The words should be in the  target language and related to the provided topics.
        The words should also be   
        The words should be within the scope of B2 level of language learning.
        Return just the list of words as a comma separated list. Do not provide translations of the words.
        Each word in the sequence should be of the part of speech as indicated in the parts of speech list.

        {format_instructions}

        Target langauge: {target_language}, topics = {topics}, parts of speech: {pos_list}
        """,
        input_variables=["target_language"],
        partial_variables={"format_instructions": word_list_json_parser.get_format_instructions(), "topics": topic_list, "pos_list":pos_list}
    )

word_list_gen_chain = word_list_gen_prompt | llm | word_list_json_parser

sentence_prompt = PromptTemplate(
    template="""    
        You are a vocabulary trainer that helps students with learning words in a foreign language.
        Create a sentence using in the target language that uses the target word in some of its forms and that is also
        indicative of intermediate B2 level in the target language
        as well as falls under the provided topic. You do not have to use the word in the exact form, but can provide a sentence, where
        the given word is in a different form (eg. different case, number, mood, tense, person, etc.)
        Provide just the sentence and nothing else. 
        Target language: {input}
        word: {word}
        topic: {topic}
    """,
    input_variables=["input", "word"],
    partial_variables={"topic": choose_topic()}
)

sentence_creation_chain = sentence_prompt | llm | str_output_parser

class EvaluationOutput(BaseModel):
    correct_translation: str = Field(description="the correct translation of the target sentence")
    sentence_evaluation: str = Field(description="evaluation of the user's sentence translation")
    sentence_eval_explanation: str = Field(description="explanation of the translation evaluation")
    word_evaluation: str = Field(description="evaluation of the target word translation by user")
    word_eval_explanation: str = Field(description="explanation of target word translation evaluation")


json_parser = JsonOutputParser(pydantic_object=EvaluationOutput)
evaluation_prompt = PromptTemplate(
    template = """Given the target sentence and the user translation and the target word, firstly, provide a correct translation for the target sentence into english,
    evaluate the user translation of the
    target sentence on a scale to from 1 to 10, provide terse 1 sentence explanation if your score is less then 10,
    then provide the the target word score on a scale from 1 to 10. If the word was translated correctly in the sentence,
    use 10, if it was translated with a slightly incorrect but semantically similar word, give 2 to 9 depending on
    similarity, if the word was not translated correctly, give 1. Provide a brief explanation to you word evaluation as well.

    {format_instructions}

    Target sentence: {target_sentence}
    Target word: {target_word}
    User translation: {translation}
    Target langauge: {language}
    """,
    input_variables=["target_sentence", "target_word", "translation", "language"],
    partial_variables={"format_instructions": json_parser.get_format_instructions()},
)

evaluation_chain = evaluation_prompt | llm | str_output_parser
