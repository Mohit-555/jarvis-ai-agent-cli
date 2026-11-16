from assistant.llm import LLM

ROUTER_PROMPT = """Classify the user request into ONE category. Reply with ONLY the category word.

Categories:
- system: System control, PC commands, CPU, memory, apps, processes, screenshots
- file: Read/write files, code, search files, run python
- web: Web search, browse pages, research, weather, news
- email: Check/manage email, inbox, messages
- github: Git, commits, pushes, PRs, issues, repositories
- codereview: Code review, analyze code quality, find bugs, suggest improvements
- general: Chat, questions, conversation, anything else

User: {query}
Category:"""

GENERAL_PROMPT = """You are Jarvis, a helpful personal AI assistant. Answer questions, have conversations, help with general tasks. Be friendly and concise."""


class Coordinator:
    def __init__(self):
        self.llm = LLM()
        self.agents = {}
        self.history = []

    def register(self, agent):
        self.agents[agent.name] = agent

    def route(self, user_input):
        try:
            resp = self.llm.chat_blocking([
                {"role": "user", "content": ROUTER_PROMPT.format(query=user_input)},
            ])
            agent_name = resp.strip().lower().split("\n")[0].strip()
            if agent_name not in self.agents:
                agent_name = "general"
        except Exception:
            agent_name = "general"

        agent = self.agents.get(agent_name)
        return agent, agent_name

    def chat(self, user_input, stream=True):
        agent, name = self.route(user_input)

        if stream:
            yield f"_Routing to **{name}**_\n\n"

        if agent:
            result = agent.chat(user_input, self.history)
        else:
            result = self._general_chat(user_input)

        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": result})

        if stream:
            for word in result.split(" "):
                yield word + " "
        else:
            return result

    def _general_chat(self, user_input):
        messages = [
            {"role": "system", "content": GENERAL_PROMPT},
            *self.history[-10:],
            {"role": "user", "content": user_input},
        ]
        return self.llm.chat_blocking(messages)

    def reset(self):
        self.history = []
