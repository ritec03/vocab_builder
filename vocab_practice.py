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

from agent import VocabularyChatAgentBuilder
from secret import OPEN_AI_KEY
from langchain_community.chat_models import ChatOpenAI

llm = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0.7, openai_api_key=OPEN_AI_KEY, streaming=False)
chat_agent_builder = VocabularyChatAgentBuilder()
agent_with_chat_history = chat_agent_builder.construct_agent(llm)


# agent interactive loop
while True:
    user_input = input()
    output = agent_with_chat_history.invoke({"input": user_input}, config={"configurable": {"session_id": "<foo>"}})
    print(output)

