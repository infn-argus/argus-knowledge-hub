"""Answering a question from the hub's own knowledge.

This is the test ARGUS has to pass. The project's claim is that structured
knowledge answers questions a pile of documents cannot — "what has gone
wrong with this magnet before, and which procedure covers it" — and the
only honest way to find out is to let somebody ask, in their own words,
and watch which records the answer actually came from.

So the tool calls are not an implementation detail to hide. They are the
output: every call and every result is returned alongside the answer, and
a question that produced a confident paragraph from no tool calls at all
is a failure, however well it reads.

The tools are the MCP ones, called in process. The same eight tools an
external assistant gets, so what is learned here is true there too.
"""
import json
import re
import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services.llm import Endpoint, LLMError, converse
from app.services.mcp_tools import BY_NAME, catalogue

# Enough hops for search → open → traverse, and a stop before a confused
# model spends a workspace's quota going in circles.
MAX_ROUNDS = 8
# What comes back from a tool can be long; the model does not need all of
# it and the context window certainly does not.
MAX_TOOL_CHARS = 12000

# Reasoning models — minimax-m27, which is what LNF points at — narrate
# their working in a <think> block and then answer. The narration is not
# the answer and must not be shown as one.
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S | re.I)
UNCLOSED_THINK = re.compile(r"<think>.*$", re.S | re.I)


def _answer_of(message: dict) -> str:
    """The answer a model meant to give, without its thinking aloud."""
    text = THINK_BLOCK.sub("", message.get("content") or "")
    # An unclosed block means it ran out of budget mid-thought; what
    # follows is nothing, and showing the monologue instead of saying so
    # is how a page passes off working-out as an answer.
    if UNCLOSED_THINK.search(text):
        text = UNCLOSED_THINK.sub("", text)
    return text.strip()

SYSTEM = (
    "You answer questions about a particle accelerator's equipment, the work done on "
    "it, and its documentation, using only the tools provided.\n\n"
    "Work from the records, never from what you know about accelerators in general. "
    "Look things up before answering — a question you think you can answer without a "
    "tool call is a question you are about to answer about some other laboratory.\n"
    "Names here are codes: equipment is called things like FI4-B-CAM-VIS-001, and the "
    "word somebody uses ('camera', 'quadrupole') is usually the type rather than the "
    "name. If a search finds nothing, try the word as a type, or a shorter fragment, "
    "before concluding there is none.\n"
    "For anything that spans records — what has failed before, what a procedure "
    "covers, what depends on what — use graph_neighbours. Searching text alone will "
    "miss it, because the answer is in no single record.\n\n"
    "Cite what you used: write the key or code of each record the answer rests on. "
    "Never invent a key, a code or a value; if the records do not say, say that they "
    "do not, and say what you looked at. An answer that sounds right and is not in "
    "the records is worse than no answer, because somebody will act on it."
)


def _tool_specs() -> list[dict]:
    """The MCP catalogue in the shape the chat API wants."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["inputSchema"],
            },
        }
        for tool in catalogue()
    ]


def _run_tool(db: Session, workspace_id: str, name: str, arguments: dict) -> tuple[str, Optional[str]]:
    """The tool's result as text, and an error message if it failed.

    A failing tool is told to the model rather than raised: a wrong
    argument is something it can correct on the next turn, and killing the
    whole question over one bad call wastes the rounds already spent.
    """
    tool = BY_NAME.get(name)
    if tool is None:
        return f"No such tool: {name}", f"No such tool: {name}"
    allowed = {
        key: value
        for key, value in (arguments or {}).items()
        if key in tool["inputSchema"].get("properties", {})
    }
    try:
        result = tool["handler"](db, workspace_id, **allowed)
    except Exception as e:  # noqa: BLE001 — reported, not swallowed
        message = f"{type(e).__name__}: {e}"
        return message, message
    return json.dumps(result, ensure_ascii=False, default=str)[:MAX_TOOL_CHARS], None


def _arguments_of(call: dict) -> dict:
    raw = (call.get("function") or {}).get("arguments")
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except ValueError:
        return {}


def ask(db: Session, workspace_id: str, endpoint: Endpoint, question: str) -> dict:
    """A question, the answer, and every record the answer was built from."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]
    tools = _tool_specs()
    steps: list[dict] = []
    started = time.monotonic()

    for _round in range(MAX_ROUNDS):
        message = converse(endpoint, messages, tools=tools)
        calls = message.get("tool_calls") or []
        if not calls:
            return {
                "answer": _answer_of(message),
                "steps": steps,
                "stopped": "answered",
                "seconds": round(time.monotonic() - started, 1),
            }

        # The assistant's own message has to go back verbatim, tool calls
        # and all, or the results that follow refer to nothing.
        messages.append({
            "role": "assistant",
            "content": message.get("content") or "",
            "tool_calls": calls,
        })

        for call in calls:
            name = (call.get("function") or {}).get("name") or ""
            arguments = _arguments_of(call)
            at = time.monotonic()
            text, error = _run_tool(db, workspace_id, name, arguments)
            steps.append({
                "tool": name,
                "arguments": arguments,
                "result": text,
                "error": error,
                "seconds": round(time.monotonic() - at, 1),
            })
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id") or name,
                "content": text,
            })

    # Out of rounds. Ask for the answer it has rather than returning
    # nothing, but say plainly that it was cut short.
    messages.append({
        "role": "user",
        "content": "Stop looking things up and answer with what you have found so far.",
    })
    try:
        final = converse(endpoint, messages)
    except LLMError as e:
        return {
            "answer": "",
            "steps": steps,
            "stopped": "exhausted",
            "error": str(e),
            "seconds": round(time.monotonic() - started, 1),
        }
    return {
        "answer": _answer_of(final),
        "steps": steps,
        "stopped": "exhausted",
        "seconds": round(time.monotonic() - started, 1),
    }
