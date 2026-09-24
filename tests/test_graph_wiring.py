"""
Offline wiring tests for the supervisor -> worker -> supervisor handoff.

These run the real compiled graph end to end with a scripted stand-in for the
LLM, so they need no API keys, no network access, and no Google credentials.
They guard the routing edges, the handoff tools (route_to_agent and
work_completion), and the per-agent message channels.

Run with:
    pytest tests/test_graph_wiring.py -v
"""

import asyncio
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core import graph as graph_module  # noqa: E402

WORKERS = [
    "communication_agent",
    "planning_agent",
    "document_agent",
    "data_agent",
]


class ScriptedLLM:
    """Stands in for a tool-bound chat model by replaying scripted replies."""

    def __init__(self, replies):
        self.replies = list(replies)

    async def ainvoke(self, messages, *args, **kwargs):
        if not self.replies:
            raise AssertionError(
                "LLM called more times than scripted: the graph re-entered a node "
                "it should have left (likely a routing loop)"
            )
        return self.replies.pop(0)


def _tool_call(name, args):
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": f"call_{name}", "type": "tool_call"}
        ],
    )


@pytest.mark.parametrize("worker", WORKERS)
def test_supervisor_hands_off_to_worker_and_gets_the_result_back(worker, monkeypatch):
    def fake_build_llm_with_tools(tools, model=None):
        if any(t.name == "route_to_agent" for t in tools):
            return ScriptedLLM(
                [
                    _tool_call(
                        "route_to_agent", {"agent": worker, "message": "do the task"}
                    ),
                    AIMessage(content="All done, SIR."),
                ]
            )
        return ScriptedLLM(
            [_tool_call("work_completion", {"message": "task finished"})]
        )

    monkeypatch.setattr(graph_module, "build_llm_with_tools", fake_build_llm_with_tools)
    tool_sets = {"communication": [], "planning": [], "content": []}
    graph = graph_module.build_graph(tool_sets, MemorySaver())

    async def _run():
        user = HumanMessage(content="please do the task")
        config = {"configurable": {"thread_id": f"wiring-{worker}"}}
        visited = []
        async for update in graph.astream(
            {"messages": [user], "supervisor_messages": [user]},
            config,
            stream_mode="updates",
        ):
            visited.extend(update.keys())
        state = (await graph.aget_state(config)).values
        return visited, state

    visited, state = asyncio.run(_run())

    tools_node = worker.replace("_agent", "_tools")
    assert visited == ["supervisor", "supervisor_tools", worker, tools_node, "supervisor"]
    assert state["current_agent"] == "supervisor"
    assert state["supervisor_messages"][-1].content == "All done, SIR."

    # The worker's result must reach the supervisor as a named handoff message.
    handoff = state["supervisor_messages"][-2]
    assert handoff.name == worker
    assert "task finished" in handoff.content
