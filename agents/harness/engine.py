"""Agent harness engine to execute ideas inside the repository workspace."""

import datetime
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from google.genai import types

import database as db
from llm import get_client
from schemas import ArchitectureCatalog, Attempt, Idea, AttemptStep, TechnicalPlan
from config import settings
from agents.planner import plan_markdown
from agents.harness.tools import (
    search_code, list_directory, view_file, edit_file, create_file, run_tests
)

logger = logging.getLogger(__name__)


def get_tool_declarations() -> types.Tool:
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="search_code",
                description="Search for a string or regex pattern in the workspace.",
                parameters={"type": "OBJECT", "properties": {"query": {"type": "STRING"}}, "required": ["query"]},
            ),
            types.FunctionDeclaration(
                name="list_directory",
                description="List contents of a directory.",
                parameters={"type": "OBJECT", "properties": {"path": {"type": "STRING"}}},
            ),
            types.FunctionDeclaration(
                name="view_file",
                description="View specific lines of a file.",
                parameters={
                    "type": "OBJECT", 
                    "properties": {
                        "path": {"type": "STRING"},
                        "start_line": {"type": "INTEGER"},
                        "end_line": {"type": "INTEGER"},
                    },
                    "required": ["path"]
                },
            ),
            types.FunctionDeclaration(
                name="edit_file",
                description="Replace an exact chunk of text in a file. target_chunk must match the file exactly.",
                parameters={
                    "type": "OBJECT", 
                    "properties": {
                        "path": {"type": "STRING"},
                        "target_chunk": {"type": "STRING"},
                        "replacement_chunk": {"type": "STRING"},
                    },
                    "required": ["path", "target_chunk", "replacement_chunk"]
                },
            ),
            types.FunctionDeclaration(
                name="create_file",
                description="Create a new file.",
                parameters={
                    "type": "OBJECT", 
                    "properties": {
                        "path": {"type": "STRING"},
                        "content": {"type": "STRING"},
                    },
                    "required": ["path", "content"]
                },
            ),
            types.FunctionDeclaration(
                name="run_tests",
                description="Run shell commands, tests, or linters.",
                parameters={"type": "OBJECT", "properties": {"command": {"type": "STRING"}}, "required": ["command"]},
            ),
            types.FunctionDeclaration(
                name="complete_attempt",
                description="Call this when the attempt is completely implemented and tested. Do not call anything else afterwards.",
                parameters={
                    "type": "OBJECT", 
                    "properties": {
                        "summary": {"type": "STRING", "description": "Markdown summary of changes"},
                        "pr_title": {"type": "STRING", "description": "Title for the PR"},
                        "testing_notes": {"type": "STRING", "description": "How the changes were tested"},
                    },
                    "required": ["summary", "pr_title", "testing_notes"]
                },
            ),
        ]
    )


class HarnessResult(BaseModel):
    success: bool
    summary: str
    pr_title: str
    testing_notes: str
    diff: str = ""
    # Outcome of the last command run in the sandbox (normally the test suite).
    test_exit_code: int | None = None
    test_output: str = ""


class AttemptHarness:
    def __init__(
        self,
        workspace: Path,
        catalog: ArchitectureCatalog,
        idea: Idea,
        attempt: Attempt,
        plan: TechnicalPlan | None = None,
    ):
        self.workspace = workspace
        self.catalog = catalog
        self.idea = idea
        self.attempt = attempt
        self.plan = plan
        self.max_steps = 25
        self.last_run = None
        self.client = get_client()

    def _log_step(self, action: str, detail: str, status: str = "completed"):
        if not self.attempt.events:
            self.attempt.events = []
        step = AttemptStep(
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            action=action,
            detail=detail,
            status=status
        )
        self.attempt.events.append(step)
        db.update_attempt(self.attempt)
        logger.info(f"Harness Step [{action}]: {detail}")

    def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        if name == "search_code":
            detail = f"Searching for '{args.get('query')}'"
        elif name in ("view_file", "edit_file", "create_file"):
            detail = f"{name} on {args.get('path')}"
        elif name == "list_directory":
            detail = f"Listing directory {args.get('path', '.')}"
        elif name == "run_tests":
            detail = f"Running tests: {args.get('command')}"
        else:
            detail = f"Executing {name}"
            
        self._log_step(name, detail)
        if name == "search_code":
            return search_code(self.workspace, args["query"])
        elif name == "list_directory":
            return list_directory(self.workspace, args.get("path", "."))
        elif name == "view_file":
            return view_file(self.workspace, args["path"], args.get("start_line", 1), args.get("end_line", 500))
        elif name == "edit_file":
            return edit_file(self.workspace, args["path"], args["target_chunk"], args["replacement_chunk"])
        elif name == "create_file":
            return create_file(self.workspace, args["path"], args["content"])
        elif name == "run_tests":
            # ponytail: last run wins; it is the test suite when the agent finishes by testing.
            self.last_run = run_tests(self.workspace, args["command"])
            return self.last_run.to_text()
        return f"Unknown tool {name}"

    def _test_outcome(self) -> dict:
        if self.last_run is None:
            return {}
        return {"test_exit_code": self.last_run.exit_code, "test_output": self.last_run.to_text()}

    def _staged_diff(self) -> str:
        """Stage every change (incl. new files) and return the staged diff."""
        git = lambda *a: subprocess.run(["git", *a], cwd=self.workspace, capture_output=True, text=True).stdout
        git("add", "-A")
        # The workspace copy skips .env/secret files; their absence must not ship as deletions.
        deleted = [p for p in git("diff", "--staged", "--name-only", "--diff-filter=D", "-z").split("\0") if p]
        if deleted:
            git("reset", "-q", "--", *deleted)
        return git("diff", "--staged")

    def run(self) -> HarnessResult:
        system_instruction = (
            "You are an autonomous senior SWE working inside a repository workspace.\n"
            "Your goal is to implement the approved idea, ground it in the architecture, and write tests.\n"
            "Explore the codebase, surgically edit files (avoid rewriting huge files), run test commands, "
            "and fix any errors before calling complete_attempt.\n"
            "Match the repo's existing style, framework and file layout.\n"
            "For every external service the idea needs (SMS, email, payments, webhooks, ...), create a "
            "runnable mock adapter named after it (e.g. mock_twilio_client.py) whose methods RETURN realistic "
            "response payloads (ids, status fields, like the real API would) and record calls. Code under test must take the adapter by injection so "
            "tests never need real credentials or network access.\n"
            "Always create test_prototype.py that exercises the new logic against those mocks, run it, and "
            "make it pass before calling complete_attempt. Never write secrets or real credentials.\n"
            f"Catalog test_command hint: {self.catalog.test_command}\n"
        )
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=
                    f"Approved Idea: {self.idea.title}\n{self.idea.description}\n"
                    f"Quote: {self.idea.quote}\n"
                    f"Catalog overview:\n{self.catalog.to_markdown()}"
                    + (f"\n\nFollow this technical plan:\n{plan_markdown(self.plan)}" if self.plan else "")
                )]
            )
        ]

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[get_tool_declarations()],
            temperature=0.1,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
        )

        model_name = settings.model_coding
        
        for step_idx in range(self.max_steps):
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                self._log_step("error", f"Model API error: {e}", status="failed")
                return HarnessResult(success=False, summary=f"API error: {e}", pr_title="", testing_notes="")

            # Always record the assistant's reply
            if response.candidates and response.candidates[0].content:
                contents.append(response.candidates[0].content)

            if not response.function_calls:
                # Prompt the model to use tools or finish
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="You must either use a tool or call complete_attempt to finish.")]
                ))
                continue

            function_responses = []
            completed = False
            result = None

            for call in response.function_calls:
                if call.name == "complete_attempt":
                    completed = True
                    args = call.args or {}
                    result = HarnessResult(
                        success=True,
                        summary=args.get("summary", "Done"),
                        pr_title=args.get("pr_title", self.idea.title),
                        testing_notes=args.get("testing_notes", ""),
                        diff=self._staged_diff(),
                        **self._test_outcome(),
                    )
                    break
                
                args = call.args or {}
                tool_output = self._execute_tool(call.name, args)
                function_responses.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response={"result": tool_output}
                    )
                )

            if completed and result:
                self._log_step("complete", "Attempt implementation finished.")
                return result

            if function_responses:
                contents.append(types.Content(
                    role="user",
                    parts=function_responses
                ))

        self._log_step("timeout", "Reached max steps without completing attempt", status="failed")
        # Fallback completion
        return HarnessResult(
            success=False,
            summary="Timed out after maximum iterations. Incomplete.",
            pr_title=self.idea.title,
            testing_notes="",
            diff=self._staged_diff(),
            **self._test_outcome(),
        )
