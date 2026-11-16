import asyncio
import re
import time
from typing import AsyncGenerator, Optional

from core.event_bus import event_bus, EVENTS
from core.exceptions import AgentError, ToolExecutionError
from core.session import Session
from llm.router import LLMRouter

from agent.planner import Planner, Step
from agent.actor import Actor, ToolResult
from agent.observer import Observer
from agent.reflector import Reflector


SYSTEM_PROMPT = """You are Jarvis, a helpful personal AI assistant that helps users with software engineering and general tasks.

# How you work
Your responses are shown directly to the user. Use GitHub-flavored markdown for formatting.
You have access to tools that let you read/write files, run shell commands, search the web, and more.
When a task requires multiple steps, the system will break it down and guide you through each step.
Tool results appear as follow-up messages. Use them to decide your next action.

# Doing tasks
- When the user asks you to write content (essay, note, email, etc.), actually GENERATE the full content yourself. Do NOT repeat the user's request as the content.
- When the user specifies a save location like "Downloads folder" or "~/Downloads/", use that EXACT path. Resolve ~ to the home directory.
- If asked to write about a topic, produce complete, well-structured content — not a placeholder or summary.
- Read a file before modifying it unless you're creating something new.
- Don't add features or make changes beyond what was asked.
- Verify your work: check that files were written to the correct path with the correct content.
- If a step fails, diagnose the error before retrying.
- Prioritize writing safe, correct code. Avoid introducing security vulnerabilities.

# Using your tools
- write_file: Write content to a file. The "content" field must be the FULL actual content (complete essay, full note, working code). NEVER use the user's query as the content.
- read_file: Read a file. Use this before editing existing files.
- open_app: Open a desktop application (calculator, clock, browser, terminal, etc.).
- shell_exec: Run shell commands. Use for package management, file operations, system commands.
- web_search: Search the web for information.
- web_fetch: Fetch the content of a URL.
- ask_user: Ask the user a question when you need clarification.

# Tone and style
- Be concise and direct. Lead with the answer or action, not the reasoning.
- Do not use emojis unless the user explicitly asks.
- Match your response to the task: simple question gets a direct answer, complex task gets a brief summary.
- In conversational text, do not wrap words, phrases, or names in markdown bold asterisks (**like this**). Use clean plain text or quotes.
- If you can say it in one sentence, don't use three."""


class AgentExecutor:
    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        tool_registry: Optional[dict] = None,
        session_manager=None,
        config: Optional[dict] = None,
    ):
        self.config = config or {}
        self.llm = llm_router
        self.tools = tool_registry or {}
        self.sessions = session_manager
        self.planner = Planner(llm_router)
        self.actor = Actor(tool_registry)
        self.observer = Observer(llm_router)
        self.reflector = Reflector()
        self.max_iterations = 10
        self._pending_ask = None
        self._ask_response = None
        self._ask_event = asyncio.Event()
        from security.permission_guard import PermissionGuard
        self.permission_guard = PermissionGuard()

    def set_mode(self, mode: str):
        self.permission_guard.set_mode(mode)

    async def execute(self, task: str, session: Session = None, config: dict = None) -> str:
        if config:
            self.config.update(config)
            if "execution_mode" in config:
                self.set_mode(config["execution_mode"])
        event_bus.emit(EVENTS["AGENT_START"], task=task, session_id=session.session_id if session else None)
        session_id = session.session_id if session else None
        context = self._get_context(session)

        try:
            steps = await self.planner.plan(task, context)
            if not steps:
                return await self._direct_llm(task)
        except Exception as e:
            event_bus.emit(EVENTS["AGENT_ERROR"], error=str(e), session_id=session_id)
            return await self._direct_llm(task)

        results = []
        for iteration in range(self.max_iterations):
            remaining = [s for s in steps if s.status == "pending"]
            if not remaining:
                break

            ready = [s for s in remaining if all(
                any(s2.id == dep and s2.status == "success" for s2 in steps)
                for dep in s.depends_on
            )]
            if not ready:
                ready = remaining[:1]

            for step in ready:
                step.status = "in_progress"
                event_bus.emit(EVENTS["AGENT_STEP"], step=step.id, description=step.description, session_id=session_id)

                if step.tool:
                    if not self.permission_guard.is_allowed(step.tool):
                        result = ToolResult(success=False, error=f"Tool execution for '{step.tool}' is denied by policy.", tool_name=step.tool)
                        step.status = "failed"
                        results.append(result)
                        continue
                    if self.permission_guard.require_confirm(step.tool):
                        result = ToolResult(success=False, error=f"Tool execution for '{step.tool}' requires confirmation, but the agent is running in non-interactive mode.", tool_name=step.tool)
                        step.status = "failed"
                        results.append(result)
                        continue

                try:
                    result = self.actor.execute_step(step, self.tools)
                    event_bus.emit(EVENTS["TOOL_RESULT"], tool=step.tool, success=result.success, session_id=session_id)
                except ToolExecutionError as e:
                    event_bus.emit(EVENTS["TOOL_ERROR"], error=str(e), session_id=session_id)
                    step.status = "failed"
                    diagnosis = self.reflector.reflect(str(e), context)
                    fix = self.reflector.suggest_fix(str(e))
                    new_steps = await self.planner.replan(step, f"{diagnosis} {fix}")
                    if new_steps:
                        steps.extend(new_steps)
                    results.append(result)
                    continue
                except Exception as e:
                    event_bus.emit(EVENTS["AGENT_ERROR"], error=str(e), session_id=session_id)
                    step.status = "failed"
                    results.append(result)
                    continue

                goal_satisfied = await self._check_goal(result, task)
                step.status = "success" if result.success else "failed"
                results.append(result)

                if goal_satisfied:
                    event_bus.emit(EVENTS["AGENT_COMPLETE"], task=task, session_id=session_id)
                    return await self._synthesize_answer_text(task, results, session)

                if not result.success:
                    diagnosis = self.reflector.reflect(result.error or "", context)
                    fix = self.reflector.suggest_fix(result.error or "")
                    new_steps = await self.planner.replan(step, f"{diagnosis} {fix}")
                    if new_steps:
                        steps.extend(new_steps)

        event_bus.emit(EVENTS["AGENT_COMPLETE"], task=task, session_id=session_id)
        return await self._synthesize_answer_text(task, results, session)

    async def execute_stream(
        self, task: str, session: Session = None, config: dict = None
    ) -> AsyncGenerator[str, None]:
        if config:
            self.config.update(config)
            if "execution_mode" in config:
                self.set_mode(config["execution_mode"])
        event_bus.emit(EVENTS["AGENT_START"], task=task, session_id=session.session_id if session else None)

        session_id = session.session_id if session else None
        context = self._get_context(session)

        _casual = re.match(
            r"^(hi|hello|hey|hii|hlo|hy|yo|sup|bye|good\s*(morning|afternoon|evening|night)|"
            r"(kya|kaise|kyu)\s*(ho|hai|hu|kar)\b|"
            r"namaste|shukriya|dhanyavad|thank|thanks|thx|ok|okay|👍|🙏|😊|👋)\s*$",
            task.strip().lower(),
        )
        if _casual or len(task.strip()) < 3:
            async for chunk in self._direct_llm_stream(task, session):
                yield chunk
            return

        try:
            steps = await self.planner.plan(task, context)
            if not steps:
                async for chunk in self._direct_llm_stream(task, session):
                    yield chunk
                return
        except Exception as e:
            async for chunk in self._direct_llm_stream(task, session):
                yield chunk
            return

        if all(s.tool == "" for s in steps):
            async for chunk in self._direct_llm_stream(task, session):
                yield chunk
            return

        is_verbose = config.get("verbose", False) if config else False

        if is_verbose:
            yield f"Planning: {task}\n"
            yield f"Created {len(steps)} steps\n"
        results = []

        READ_ONLY_TOOLS = {"read_file", "web_search", "web_fetch", "list_directory", "system_info", "clipboard_read", "process_list", "open_app", "screenshot"}

        for iteration in range(self.max_iterations):
            remaining = [s for s in steps if s.status == "pending"]
            if not remaining:
                break

            ready = []
            for s in remaining:
                deps = [s2 for s2 in steps if s2.id in s.depends_on]
                if all(d.status == "success" for d in deps):
                    ready.append(s)

            # Batch independent read-only tools for parallel execution
            read_batch = [s for s in ready if s.tool in READ_ONLY_TOOLS]
            write_batch = [s for s in ready if s.tool not in READ_ONLY_TOOLS]

            if read_batch:
                if is_verbose:
                    yield f"\nStep(s): {', '.join(s.id for s in read_batch)} ({', '.join(s.description for s in read_batch)})\n"
                async def run_read_tool(step):
                    step.status = "in_progress"
                    event_bus.emit(EVENTS["AGENT_STEP"], step=step.id, description=step.description, tool=step.tool, session_id=session_id)
                    try:
                        r = self.actor.execute_step(step, self.tools)
                        return step, r
                    except Exception as e:
                        return step, ToolResult(success=False, error=str(e), tool_name=step.tool)

                read_results = await asyncio.gather(*[run_read_tool(s) for s in read_batch])
                for step, result in read_results:
                    step.status = "success" if result.success else "failed"
                    results.append(result)
                    if is_verbose:
                        if result.success:
                            yield f"  [{step.id}] {str(result.data)[:2000]}\n"
                        else:
                            yield f"  [{step.id}] Error: {result.error}\n"

                    goal_satisfied = await self._check_goal(result, task)
                    if goal_satisfied:
                        event_bus.emit(EVENTS["AGENT_COMPLETE"], task=task, session_id=session_id)
                        if is_verbose:
                            yield "\nGoal satisfied!\n\n"
                        async for chunk in self._synthesize_answer(task, results, session):
                            yield chunk
                        return

            for step in write_batch:
                step.status = "in_progress"
                event_bus.emit(EVENTS["AGENT_STEP"], step=step.id, description=step.description, tool=step.tool, session_id=session_id)
                if is_verbose:
                    yield f"\nStep {step.id}: {step.description}\n"

                if step.tool == "ask_user":
                    question = step.args.get("question", step.description)
                    self._pending_ask = question
                    self._ask_event.clear()
                    yield ""
                    await self._ask_event.wait()
                    answer = self._ask_response
                    self._pending_ask = None
                    self._ask_response = None
                    result = ToolResult(success=True, data=answer, tool_name="ask_user")
                else:
                    if step.tool:
                        if not self.permission_guard.is_allowed(step.tool):
                            result = ToolResult(success=False, error=f"Tool execution for '{step.tool}' is denied by policy.", tool_name=step.tool)
                            step.status = "failed"
                            yield f"Execution of '{step.tool}' is denied by safety policy.\n"
                            results.append(result)
                            continue
                        if self.permission_guard.require_confirm(step.tool):
                            question = f"Do you want to run '{step.tool}' with arguments {step.args}? (y/n)"
                            self._pending_ask = question
                            self._ask_event.clear()
                            yield ""
                            await self._ask_event.wait()
                            answer = (self._ask_response or "").strip().lower()
                            self._pending_ask = None
                            self._ask_response = None
                            if answer not in ("y", "yes"):
                                result = ToolResult(success=False, error="Tool execution denied by user.", tool_name=step.tool)
                                step.status = "failed"
                                yield f"Execution denied by user.\n"
                                results.append(result)
                                continue

                    try:
                        result = self.actor.execute_step(step, self.tools)
                        if is_verbose:
                            yield f"Result: {str(result.data)[:2000]}\n"
                        step.status = "success" if result.success else "failed"
                    except Exception as e:
                        step.status = "failed"
                        if is_verbose:
                            yield f"Error: {e}\n"
                        diagnosis = self.reflector.reflect(str(e), context)
                        fix = self.reflector.suggest_fix(str(e))
                        if is_verbose:
                            yield f"Diagnosis: {diagnosis}\nFix: {fix}\n"
                        new_steps = await self.planner.replan(step, f"{diagnosis} {fix}")
                        if new_steps:
                            steps.extend(new_steps)
                            if is_verbose:
                                yield f"Created {len(new_steps)} recovery steps\n"
                        results.append(result)
                        continue

                if step.tool != "ask_user":
                    goal_satisfied = await self._check_goal(result, task)
                    if goal_satisfied:
                        results.append(result)
                        event_bus.emit(EVENTS["AGENT_COMPLETE"], task=task, session_id=session_id)
                        if is_verbose:
                            yield "\nGoal satisfied!\n\n"
                        async for chunk in self._synthesize_answer(task, results, session):
                            yield chunk
                        return

                    if result.success:
                        remaining = [s for s in steps if s.status == "pending"]
                        if not remaining:
                            new_steps = await self.planner.plan(task, f"{context}\nStep result: {str(result.data)[:3000]}")
                            if new_steps and not all(s.tool == "" for s in new_steps):
                                steps.extend(new_steps)
                                if is_verbose:
                                    yield f"Re-planned: {len(new_steps)} additional steps\n"
                    else:
                        diagnosis = self.reflector.reflect(result.error or "", context)
                        fix = self.reflector.suggest_fix(result.error or "")
                        if is_verbose:
                            yield f"Diagnosis: {diagnosis}\nFix: {fix}\n"
                        new_steps = await self.planner.replan(step, f"{diagnosis} {fix}")
                        if new_steps:
                            steps.extend(new_steps)
                            if is_verbose:
                                yield f"Created {len(new_steps)} recovery steps\n"
                else:
                    step.status = "success"
                    new_steps = await self.planner.plan(task, f"{context}\nUser answer: {result.data}")
                    if new_steps:
                        steps.extend(new_steps)
                        if is_verbose:
                            yield f"Created {len(new_steps)} follow-up steps\n"
                results.append(result)

        event_bus.emit(EVENTS["AGENT_COMPLETE"], task=task, session_id=session_id)
        if is_verbose:
            yield f"\nCompleted {len(results)} steps\n\n"
        async for chunk in self._synthesize_answer(task, results, session):
            yield chunk

    async def _synthesize_answer(
        self, task: str, results: list[ToolResult], session: Session = None
    ) -> AsyncGenerator[str, None]:
        if not results:
            return

        if not self.llm:
            for r in results:
                if r.data:
                    yield str(r.data)
            return

        tool_outputs = []
        for r in results:
            status = "Success" if r.success else "Failed"
            data = r.data if r.success else r.error
            tool_outputs.append(f"Tool: {r.tool_name}\nStatus: {status}\nOutput: {str(data)[:3000]}")
        formatted_tools = "\n\n".join(tool_outputs)

        user_name = self.config.get("user_name") if self.config else None
        user_lang = self.config.get("user_language") if self.config else None
        user_directive = ""
        if user_name:
            user_directive += f"Address the user ({user_name}) naturally by name.\n"
        if user_lang:
            if user_lang.lower() == "hinglish":
                user_directive += f"Respond in conversational Hinglish (Hindi written in Latin script, e.g. 'Haan {user_name or 'User'}, maine check kar liya hai.').\n"
            else:
                user_directive += f"Respond in clear {user_lang}.\n"

        prompt = (
            f"You are Jarvis, a personal AI assistant.\n"
            f"Answer the user's request directly, concisely, and naturally using the tool results below.\n"
            f"Do NOT mention internal tool names (like run_python, shell_exec) or steps unless the user explicitly asked for code or commands.\n"
            f"Do NOT wrap words, phrases, or names in markdown bold asterisks (**like this**) in conversational sentences. Use clean plain text.\n"
            f"{user_directive}"
            f"Match the language of the user (e.g. Hindi, Hinglish, or English).\n\n"
            f"User request: {task}\n\n"
            f"Tool execution results:\n{formatted_tools}\n\n"
            f"Direct Answer:"
        )

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        try:
            has_content = False
            async for chunk in self.llm.generate_stream(messages):
                if chunk:
                    has_content = True
                    yield chunk
            if not has_content:
                for r in results:
                    if r.data:
                        yield str(r.data)
        except Exception:
            for r in results:
                if r.data:
                    yield str(r.data)

    async def _synthesize_answer_text(
        self, task: str, results: list[ToolResult], session: Session = None
    ) -> str:
        acc = ""
        async for chunk in self._synthesize_answer(task, results, session):
            acc += chunk
        return acc.strip() or self._format_results(results)

    async def _check_goal(self, result: ToolResult, task: str) -> bool:
        if not result.success:
            return False
        # Use our advanced Observer to evaluate if the goal is satisfied
        obs = await self.observer.analyze_result(result, task)
        return obs.goal_satisfied

    def submit_answer(self, answer: str):
        self._ask_response = answer
        self._ask_event.set()

    async def _direct_llm_stream(self, task: str, session: Session = None) -> AsyncGenerator[str, None]:
        if not self.llm:
            yield "No LLM available to process this task."
            return
        try:
            async for chunk in self.llm.generate_stream(self._build_messages(task, session)):
                yield chunk
        except Exception as e:
            yield f"LLM error: {e}"

    async def _direct_llm(self, task: str, session: Session = None) -> str:
        if not self.llm:
            return "No LLM available to process this task."
        try:
            return await self.llm.generate(self._build_messages(task, session))
        except Exception as e:
            return f"Hello! I'm having trouble connecting right now (LLM error: {e}). Please try again shortly."

    def _get_system_prompt(self) -> str:
        prompt = SYSTEM_PROMPT
        user_name = self.config.get("user_name") if self.config else None
        user_lang = self.config.get("user_language") if self.config else None
        if user_name or user_lang:
            prompt += "\n\n# User Profile & Language Preference\n"
            if user_name:
                prompt += f"- User's Name: {user_name}\n"
                prompt += f"- Always remember the user's name is {user_name}. Naturally address the user by their name ({user_name}) during conversations (for greetings, confirmations, task completions, and answers).\n"
            if user_lang:
                prompt += f"- Preferred Language: {user_lang}\n"
                if user_lang.lower() == "hinglish":
                    prompt += "- You MUST communicate in conversational Hinglish (Hindi written in English/Latin script, e.g. 'Haan {name}, maine check kar liya hai.'). Mix Hindi and English naturally.\n"
                elif user_lang.lower() == "english":
                    prompt += "- You MUST communicate in clear, natural English.\n"
        return prompt

    def _build_messages(self, task: str, session: Session = None) -> list[dict]:
        """Build full message history: system prompt + conversation history + current user message."""
        messages = [{"role": "system", "content": self._get_system_prompt()}]

        if session:
            # Include up to the last 20 turns (excluding the current user message which we add separately)
            history = session.get_context(limit=20)
            # The current user message was already added to session by cli.py before calling execute_stream,
            # so skip the last message (it's the current user turn) to avoid duplication.
            past = history[:-1] if history and history[-1].get('role') == 'user' and history[-1].get('content') == task else history
            for msg in past:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                # Only include user and assistant roles (skip system/tool messages)
                if role in ('user', 'assistant') and content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": task})
        return messages

    def _get_context(self, session: Session = None) -> str:
        if not session:
            return ""
        return "\n".join(
            f"{m['role']}: {m['content']}" for m in session.get_context(limit=5)
        )

    def _format_results(self, results) -> str:
        parts = []
        for i, r in enumerate(results):
            status = "\u2713" if r.success else "\u2717"
            parts.append(f"[{status}] Step {i+1}: {str(r.data or r.error)[:2000]}")
        return "\n".join(parts)
