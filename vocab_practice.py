"""
Ask the agent to practice certain words on  a topic?

Student state - list of words with scores indicating knowledge

Interaction:
* lesson
    * Student initializes a lesson.
    * ten random words are returned from the student state that have the lowest ranking
    * the words are passed to the agent, which generates a sentence for each word
    * learning stage:
        * 
"""

import json
from langchain_community.chat_models import ChatOpenAI
from secret import OPEN_AI_KEY
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import random


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

# topic = choose_topic()
# print("My topic is ", topic)


llm = ChatOpenAI(openai_api_key=OPEN_AI_KEY)
# print(llm.invoke("how can langsmith help with testing?"))
# print("I am here")


from langchain.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a vocabulary trainer that helps students with learning words in a foreign language.",
        ),
        (
            "user",
            "Translate a the input word into the target langauge. Just provide the translation and nothing else. Target language: {input}, word: {word}",
        ),
    ]
)

sentence_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a vocabulary trainer that helps students with learning words in a foreign language.",
        ),
        (
            "user",
            """Create a sentence using in the target language that uses the target word in some of its forms and that is also
            indicative of intermediate B2 level in the target language
            as well as falls under the provided topic. You do not have to use the word in the exact form, but can provide a sentence, where
            the given word is in a different form (eg. different case, number, mood, tense, person, etc.)
            Provide just the sentence and nothing else. 
            Target language: {input}
            word: {word}
            topic: {topic}
            """,
        ),
    ]
)

evaluation_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a vocabulary trainer that helps students with learning words in a foreign language.",
        ),
        (
            "user",
            """Given the target sentence and the input translation and the target word, firstly, provide a correct translation for the target sentence into english,
    evaluate the translation of the
    target sentence on a scale to from 1 to 10, provide terse 1 sentence explanation if your score is less then 10,
    then provide the the target word score on a scale from 1 to 10. If the word was translated correctly in the sentence,
    use 10, if it was translated with a slightly incorrect but semantically similar word, give 2 to 9 depending on
    similarity, if the word was not translated correctly, give 1. Provide a brief explanation to you word evaluation as well.
    Lastly, 

    Provide the output as a json string with keys: correct_translation, sentence_evaluation, sentence_eval_explanation, word_evaluation, word_eval_explanation.

    Target sentence: {target_sentence}
    Target word: {target_word}
    Translation: {translation}
    Target langauge: {language}
    """,
        ),
    ]
)

output_parser = StrOutputParser()

chain = prompt | llm | output_parser
sentence_creation_chain = sentence_prompt | llm | output_parser
evaluation_chain = evaluation_prompt | llm | output_parser

# output = chain.invoke({"input": "german", "word": "to order"})
# print(output)

# output_2 = sentence_creation_chain.invoke({"input": "german", "word": output, "topic": topic})
# print(output_2)

# output_3 = evaluation_chain.invoke(
#     {
#         "language": "german",
#         "target_sentence": "Ich möchte eine Pizza bestellen, bitte.",
#         "translation": "I would like to order Pizza",
#         "target_word": "bestellen",
#     }
# )
# print(output_3)

"""
we have a chain that takes a word, translates it
we have a chain that takes a word in german and creates a sentence with it
we have a chain that takes a sentence and a transaltion and a word and evaluates the translation

Now we need: 
* something that actually chooses the words or requests word inputs
    * 

Example interaction:
1. User starts a new lesson and either chooses category or inputs a list of words that the user wants to learn.
2. The bot constructs a word bucket to be trained during the session.
3. The bot starts to construct sentences (or pull sentences for the word if some already exist)
4. The user performs a task on the constructed sentence. For now, just stick with translation task.

How to create an interactive interface?
* Create an agent that will guide the user to starting the session.
    * The agent will either create words to study, or get input from the user about the words.
    * The agent will then start ??? a chain on the word list that will guide the user???
    * save the state from the session.
    * provide summary of the session.

    
This will require:
* creating a dummy interactive CL application
* figure out how to accept and wait for human input in LangChain chains?
    * or simply construct an application around it.
"""


# create the main agent and tools
# tools - create the list, lesson chains

"""
Lesson chains
* give sentence
* get translation
* provide feedback and store result
* after all words are done - return to the main agent with the results

Chain 1 - provide sentence
Chain 2 - evaluate result
"""


from langchain.tools import tool
from secret import OPEN_AI_KEY

# tool - create vocabulary list
@tool
def generate_vocabulary_list(target_language: str) -> str:
    """This generates a list of ten words (vocabulary list) to be learned by the user
    in a lesson if hte user did not provide their list."""

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a vocabulary trainer that helps students with learning words in a foreign language.",
            ),
            (
                "user",
                """Create a list of ten words in the target language that are useful to learn for a learner
                at the intermediate (B2) level. Return just the list of words as a comma separated list.
                Return Target langauge: {target_language}, topics = {topics}
                """,
            ),
        ]
    )
    chain = prompt | llm | output_parser

    output = chain.invoke({"target_language": target_language, "topics": [choose_topic(), choose_topic(), choose_topic()]})

    return output 

@tool
def perform_vocabulary_practice(user_input: str):
    """Provided a list of words, performs a vocabulary practice session
    on these words.
    
    Example user_input type is a JSON string with schema {words: list[str], target_langauge: str}
    """
    print("Lesson user_input ", user_input)
    user_input: {"words": list[str], "target_language": str} = json.loads(user_input) 
    for word in user_input["words"]:
        # chain for sentence generation
        sentence = sentence_creation_chain.invoke({"input": user_input["target_language"], "word": word, "topic": choose_topic()})
        # get human input
        print(sentence)
        user_translation = input("Translate this sentence\n")
        # chain for translation evaluation
        # provides json string with these keys:
        # correct_translation, sentence_evaluation, sentence_eval_explanation, word_evaluation, word_eval_explanation
        evaluation = evaluation_chain.invoke(
            {
                "language": user_input["target_language"],
                "target_sentence": sentence,
                "translation": user_translation,
                "target_word": word,
            }
        )
        print(evaluation)


tools = [generate_vocabulary_list, perform_vocabulary_practice]


from langchain import hub
from langchain_community.chat_models import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from secret import OPEN_AI_KEY
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.prompts import SystemMessagePromptTemplate, ChatPromptTemplate, PromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate

from tools import Response, retriever_tool, return_user_package_info, get_user_package_level, parse
from langchain.utils.openai_functions import convert_pydantic_to_openai_function
from langchain_community.tools.convert_to_openai import format_tool_to_openai_function
from langchain.agents.format_scratchpad import format_to_openai_function_messages

class ChatAgentBuilder:
    def __init__(self, streaming=False, system_message=None):
        self.streaming = streaming
        self.system_message = system_message or self.get_default_system_message()

    def get_default_system_message(self):
        return """
        You are a helpful vocabulary building assistant. You help students of foreign languages
        to build their vocabulary through deliberate practice. At the start of the conversation, 
        you need to ask the user if they want to start a practice session, if they do, then you
        need ask them to provide a word list, or to generate the word list automatically. Then
        you also need to ask what language they want to practice.
        """

    def construct_agent(self):
        prompt = hub.pull("hwchase17/openai-tools-agent")

        prompt.messages = [
            SystemMessagePromptTemplate(prompt=PromptTemplate(input_variables=[], template=self.system_message)),
            MessagesPlaceholder(variable_name='chat_history', optional=True),
            HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=['input'], template='{input}')),
            MessagesPlaceholder(variable_name='agent_scratchpad')
        ]
        message_history = ChatMessageHistory()

        llm = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0.7, openai_api_key=OPEN_AI_KEY, streaming=self.streaming)

        agent = create_openai_tools_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

        agent_with_chat_history = RunnableWithMessageHistory(
            agent_executor,
            # This is needed because in most real-world scenarios, a session id is needed
            # It isn't really used here because we are using a simple in-memory ChatMessageHistory
            lambda session_id: message_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

        return agent_with_chat_history
    

chat_agent_builder = ChatAgentBuilder(streaming=True)
agent_with_chat_history = chat_agent_builder.construct_agent()


# agent interactive loop
while True:
    user_input = input()
    output = agent_with_chat_history.invoke({"input": user_input}, config={"configurable": {"session_id": "<foo>"}})
    print(output)

