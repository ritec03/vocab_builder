
from langchain import hub
from langchain_community.chat_models import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.prompts import SystemMessagePromptTemplate, PromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate
from agent_tools import tools

class VocabularyChatAgentBuilder:
    def __init__(self, system_message=None):
        self.system_message = system_message or self.get_default_system_message()

    def get_default_system_message(self):
        return """
        You are a helpful vocabulary building assistant. You help students of foreign languages
        to build their vocabulary through deliberate practice. At the start of the conversation, 
        you need to ask the user to provide a word list, or to generate the word list automatically. Then
        you also need to ask what language they want to practice.
        """

    def construct_agent(self, llm: ChatOpenAI):
        prompt = hub.pull("hwchase17/openai-tools-agent")

        prompt.messages = [
            SystemMessagePromptTemplate(prompt=PromptTemplate(input_variables=[], template=self.system_message)),
            MessagesPlaceholder(variable_name='chat_history', optional=True),
            HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=['input'], template='{input}')),
            MessagesPlaceholder(variable_name='agent_scratchpad')
        ]
        message_history = ChatMessageHistory()
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
    