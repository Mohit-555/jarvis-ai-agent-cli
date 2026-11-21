import os
import asyncio
import re
import time
from pathlib import Path
from typing import AsyncGenerator, Optional

from core.event_bus import event_bus, EVENTS
from core.exceptions import AgentError, ToolExecutionError
from core.session import Session
from core.logger import central_logger
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
- scan_project: Intelligently and securely scan a project directory to discover its architecture, entry points (.py, main.py, app.py), dependencies (requirements.txt, pyproject.toml), and file tree while ignoring sensitive dotfiles, browser profiles, and caches.
- db_query / db_list_tables / db_export_csv: Execute SQL queries, list tables, and export data to CSV across SQLite, MySQL, and PostgreSQL.
- doc_read / doc_generate / doc_convert: Read, generate, and convert Word (.docx), Excel (.xlsx), PDF (.pdf), PowerPoint (.pptx), and CSV files.
- whatsapp_send: Send a WhatsApp message to a phone number or contact name.
- whatsapp_send_file: Send a document, PDF, image, video, or file on WhatsApp Web with an optional caption.
- whatsapp_check_unread: Check how many unread chats exist on WhatsApp Web.
- whatsapp_read_unread: Read recent incoming unread messages from WhatsApp Web.
- whatsapp_read_chat: Read recent messages from a specific contact on WhatsApp.
- whatsapp_search_contact: Search a contact or phone number on WhatsApp Web to find out whose number it is.
- email_read_inbox / email_search / email_read: Read and search your personal email inbox.
- calendar_list_events / calendar_create_event: Manage and list Google Calendar events.
- git_status / git_diff / git_log / git_commit / git_push / git_pull / git_branch / git_checkout / git_stash / git_clone / git_run: Perform local Git operations (status, diff, log, commit, push, pull, branch, stash, clone, arbitrary git commands).
- github_create_pr / github_list_prs / github_view_pr / github_merge_pr: Manage GitHub Pull Requests via GitHub CLI (`gh`).
- github_create_issue / github_list_issues / github_view_issue / github_close_issue / github_repo_view / github_run: Manage GitHub issues and repository details.
- write_file: Write content to a file. The "content" field must be the FULL actual content.
- read_file: Read a file. Use this before editing existing files.
- open_app: Open a desktop application (calculator, clock, brave browser, terminal, etc.).
- shell_exec: Run shell commands.
- web_search: Search the web for information.
- web_fetch: Fetch the content of a URL.
- ask_user: Ask the user a question when you need clarification.

You HAVE integrated capabilities to interact with WhatsApp Web, personal emails, Google Calendar, local files, Git repositories, GitHub (via gh CLI), shell commands, and the browser using your tools. If the user asks whether you can access WhatsApp or perform Git/GitHub operations, answer YES and explain what actions you can perform. Never claim you lack access.

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
        summary = central_logger.start_request(task)

        try:
            steps = await self.planner.plan(task, context)
            if not steps:
                res = await self._direct_llm(task)
                summary.complete("success")
                return res
        except Exception as e:
            event_bus.emit(EVENTS["AGENT_ERROR"], error=str(e), session_id=session_id)
            summary.complete("failed", error=str(e))
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
        summary = central_logger.start_request(task)

        if self._is_direct_chat(task):
            async for chunk in self._direct_llm_stream(task, session):
                yield chunk
            summary.complete("success")
            return

        try:
            steps = await self.planner.plan(task, context)
            if not steps:
                async for chunk in self._direct_llm_stream(task, session):
                    yield chunk
                summary.complete("success")
                return
        except Exception as e:
            central_logger.log_error(f"Execution planning error: {e}", exc_info=True)
            async for chunk in self._direct_llm_stream(task, session):
                yield chunk
            summary.complete("failed", error=str(e))
            return

        if all(s.tool == "" for s in steps):
            async for chunk in self._direct_llm_stream(task, session):
                yield chunk
            summary.complete("success")
            return

        is_verbose = config.get("verbose", False) if config else False

        if is_verbose:
            yield f"Planning: {task}\n"
            yield f"Created {len(steps)} steps\n"
        results = []

        READ_ONLY_TOOLS = {"read_file", "web_search", "web_fetch", "list_directory", "scan_project", "db_query", "db_list_tables", "doc_read", "system_info", "clipboard_read", "process_list", "open_app", "screenshot", "get_current_media"}

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
                    question_text = step.args.get("question", step.description) if isinstance(step.args, dict) else step.description
                    options = list(step.args.get("options", [])) if isinstance(step.args, dict) else []
                    multiple = bool(step.args.get("multiple", False)) if isinstance(step.args, dict) else False
                    title = step.args.get("title", "Jarvis needs your input") if isinstance(step.args, dict) else "Jarvis needs your input"

                    if not options:
                        q_lower = question_text.lower()
                        if "website" in q_lower:
                            options = ["E-commerce", "Portfolio", "Blog", "Business Website", "Student Management System", "Other"]
                        elif any(w in q_lower for w in ("language", "framework", "tech stack")):
                            options = ["Python / Django", "FastAPI", "React / Node.js", "Vue.js", "Other"]
                        elif any(w in q_lower for w in ("database", "db")):
                            options = ["SQLite", "PostgreSQL", "MySQL", "MongoDB", "Other"]
                        elif any(w in q_lower for w in ("confirm", "proceed", "yes or no", "approve")):
                            options = ["Yes, proceed", "No, cancel", "Modify plan"]

                    q_payload = {
                        "type": "select" if options else "text",
                        "title": title,
                        "progress": f"Question {step.id} of {len(steps)}",
                        "question": question_text,
                        "options": options,
                        "multiple": multiple,
                        "required": True,
                    }

                    import json
                    self._pending_ask = q_payload
                    self._ask_event.clear()
                    event_bus.emit(EVENTS["AGENT_ASK"], question=q_payload, step=step.id, session_id=session_id)
                    central_logger.agent_logger.info(f"User interaction requested: '{question_text}' (options={len(options)})")
                    yield f"[ASK_STRUCT:{json.dumps(q_payload)}]\n"
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
                            question = f"Do you want to run '{step.tool}' with arguments {step.args}?"
                            q_payload = {
                                "type": "select",
                                "title": "Tool Execution Confirmation",
                                "question": question,
                                "options": ["Yes, allow execution", "No, deny"],
                                "multiple": False,
                                "required": True,
                            }
                            import json
                            self._pending_ask = q_payload
                            self._ask_event.clear()
                            event_bus.emit(EVENTS["AGENT_ASK"], question=q_payload, step=step.id, session_id=session_id)
                            yield f"[ASK_STRUCT:{json.dumps(q_payload)}]\n"
                            await self._ask_event.wait()
                            answer = (self._ask_response or "").strip().lower()
                            self._pending_ask = None
                            self._ask_response = None
                            if not any(yes in answer for yes in ("y", "yes", "allow")):
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
        event_bus.emit(EVENTS["USER_RESPONSE"], answer=answer)
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
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        jarvis_home = os.path.expanduser("~/.jarvis")
        prompt += f"\n\n# System Environment & Workspace Guidelines\n"
        prompt += f"- Current Working Directory: {cwd}\n"
        prompt += f"- User Home Directory: {home}\n"
        prompt += f"- Jarvis Internal User Data Directory: {jarvis_home} (stores internal Jarvis logs, configs, databases, and session profiles). NEVER treat this directory or Jarvis agent source files as the user's application project!\n"
        prompt += "\n# AI Coding Agent Behavior & Protocol\n"
        prompt += "- Purpose Explanation: Whenever you need to inspect files or directories, ALWAYS explain the exact purpose before taking action (e.g. 'I am inspecting your project structure to understand existing modules and locate the optimal place for your function').\n"
        prompt += "- Workspace vs Jarvis Distinction: If the user asks you to write code, modify code, or inspect their project, and the current working directory is Jarvis's own internal repository or runtime folder and NOT their target application, explicitly inform them:\n"
        prompt += "  'I've located your Jarvis directory. However, I haven't identified your actual application source code yet. Please provide the project directory or select a project from your workspace. I'll inspect its Python files, understand the existing architecture, and identify the best location to add your requested function. I won't modify any files without your confirmation.'\n"
        prompt += "- Intelligent File Scanning: Use `scan_project` to inspect codebases. Prioritize high-signal files: .py, main.py, app.py, config.py, requirements.txt, pyproject.toml, and project source folders. Strictly avoid mentioning or scanning .bashrc, shell configs, browser profiles, API keys, session data, or credentials.\n"
        prompt += "- Safety & Confirmation Protocol: First inspect architecture and identify the best design/location. Never modify, overwrite, or delete project files without explicit confirmation from the user.\n"

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

    def _is_direct_chat(self, task: str) -> bool:
        """Determine if a user query is conversational or informational, bypassing multi-step planner."""
        t = task.strip().lower()
        t_clean = re.sub(r"[?!.,;:~_]+", "", t).strip()

        # 1. Greetings & common chit-chat
        casual_exact = {
            "hi", "hello", "hey", "hii", "hiii", "hlo", "hy", "yo", "sup", "bye", "goodbye",
            "good morning", "good afternoon", "good evening", "good night",
            "namaste", "namaskar", "shukriya", "dhanyavad", "thank you", "thanks", "thx",
            "ok", "okay", "alright", "got it", "cool", "nice", "great", "sure",
            "kya haal hai", "kaise ho", "kya chal raha hai", "sab theek", "aur batao",
            "who are you", "what are you", "what can you do", "introduce yourself", "tell me about yourself",
            "what's your name", "whats your name", "tum kaun ho", "aap kaun ho"
        }
        if t_clean in casual_exact or len(t_clean) < 3:
            return True

        # 2. Greeting with name or common follow-up (e.g. "hi jarvis", "hello buddy, how are you?", "hey jarvis what's up")
        if re.match(r"^(hi|hello|hey|hii|namaste|hlo)\b[\s\w,!-]*\b(jarvis|bro|buddy|friend|bhai)?[\s,!-]*([?]|how are you|kya haal|who are you|kaise ho|what's up|whats up|help me)?\s*$", t):
            return True

        # 3. Questions about agent capabilities (e.g. "do you have ability to see in whatsapp", "can you read emails")
        if any(p in t for p in ["ability", "can you", "kya tum", "kya aap", "capabilities", "features", "kya kar sakte"]):
            return True

        # 4. If query mentions phone numbers or tools, require the tool planner
        if re.search(r"\b\d{7,}\b", t):
            return False
        if any(w in t for w in ["whatsapp", "whtsapp", "email", "gmail", "inbox", "calendar", "git", "github", "commit", "push", "pull", "repo", "branch"]):
            return False

        # 3. Action keywords that strictly require the tool planner
        action_keywords = [
            "open ", "launch ", "start app", "close app",
            "run ", "exec ", "execute ", "terminal", "bash", "shell",
            "create file", "write file", "make a file", "save to", "save this to",
            "delete file", "remove file", "read file", "list directory", "list files", "ls -",
            "search web", "google ", "web search", "browse ", "fetch url", "download ",
            "screenshot", "kill process", "check cpu", "system status", "set volume",
            "git ", "commit ", "push ", "pull ", "branch ", "checkout ", "stash "
        ]
        if any(k in t for k in action_keywords):
            return False

        # 4. Pure informational or question queries without filesystem/command instructions
        info_starters = [
            "what is", "what are", "who is", "who was", "where is", "why is", "why does",
            "tell me a", "tell me about", "explain", "how does", "summarize",
            "write a poem", "write a story", "write an essay", "translate",
            "kya hai", "kaise hota hai", "samjhao", "batao", "joke sunao"
        ]
        if any(t.startswith(s) for s in info_starters):
            if not any(k in t for k in ["save", "file", "folder", "open", "run", "terminal", "command", "download"]):
                return True

        return False

    def _build_messages(self, task: str, session: Session = None) -> list[dict]:
        """Build full message history: system prompt + conversation history + current user message."""
        messages = [{"role": "system", "content": self._get_system_prompt()}]

        if session:
            # Include up to the last 10 turns (compact payload for faster LLM response)
            history = session.get_context(limit=10)
            # The current user message was already added to session by cli.py before calling execute_stream,
            # so skip the last message (it's the current user turn) to avoid duplication.
            past = history[:-1] if history and history[-1].get('role') == 'user' and history[-1].get('content') == task else history
            for msg in past:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role in ('user', 'assistant') and content:
                    # Truncate giant past messages (e.g. huge code/log dumps) to keep prompt fast
                    trimmed = content[:600] + " ...[truncated]" if len(content) > 600 else content
                    messages.append({"role": role, "content": trimmed})

        messages.append({"role": "user", "content": task})
        return messages

    def _get_context(self, session: Session = None) -> str:
        ctx_parts = [
            f"Current Working Directory: {os.getcwd()}",
            f"User Home Directory: {os.path.expanduser('~')}",
            f"Jarvis Data Directory: {os.path.expanduser('~/.jarvis')}",
        ]
        if session:
            chat_hist = "\n".join(
                f"{m['role']}: {m['content']}" for m in session.get_context(limit=5)
            )
            if chat_hist:
                ctx_parts.append(f"Recent Chat History:\n{chat_hist}")
        return "\n".join(ctx_parts)

    def _format_results(self, results) -> str:
        parts = []
        for i, r in enumerate(results):
            status = "\u2713" if r.success else "\u2717"
            parts.append(f"[{status}] Step {i+1}: {str(r.data or r.error)[:2000]}")
        return "\n".join(parts)
