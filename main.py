import asyncio
import threading
import time
from datetime import datetime

import aiosqlite
import langchain_core.tools.base
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

if not hasattr(langchain_core.tools.base, "TOOL_MESSAGE_BLOCK_TYPES"):
    langchain_core.tools.base.TOOL_MESSAGE_BLOCK_TYPES = (
        "text",
        "image_url",
        "image",
        "json",
        "search_result",
        "custom_tool_call_output",
        "document",
        "file",
    )

from app_tools.core.server_init import (
    communication_server,
    planning_server,
    content_server,
)

# Import tools 
import app_tools.tools.google.gmail_tools
import app_tools.tools.google.calendar_tools
import app_tools.tools.google.gsheet_tools
import app_tools.tools.google.gdocs_tools
import app_tools.tools.google.gtask_tools

from config.settings import CHECKPOINT_DB, DEFAULT_THREAD_ID
from core.graph import build_graph
from rich.markdown import Markdown
from rich.panel import Panel
from utils.helper import console, request_counter, setup_logger

logger = setup_logger(__name__)


AGENT_MESSAGE_KEY = {
    "supervisor": "supervisor_messages",
    "communication_agent": "communication_messages",
    "planning_agent": "planning_messages",
    "document_agent": "document_messages",
    "data_agent": "data_messages",
}


def keyword_listener(
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
    agent_state,
    turn_ready: threading.Event,
):
    """Read stdin on a dedicated daemon thread."""
    while True:
        turn_ready.wait()
        try:
            console.print("\n[bold #D97757]You[/] [bold #D97757]❯[/] ", end="")
            user_input = input()
        except (EOFError, KeyboardInterrupt):
            try:
                asyncio.run_coroutine_threadsafe(
                    queue.put(("TEXT", "exit")), loop
                ).result()
            except Exception:
                pass
            break
        except Exception as e:
            logger.error(f"Error in keyword listener: {e}")
            continue

        if not user_input.strip():
            continue

        turn_ready.clear()
        agent_state["last_interaction"] = time.time()
        try:
            asyncio.run_coroutine_threadsafe(
                queue.put(("TEXT", user_input.strip())), loop
            ).result()
        except Exception as e:
            logger.error(f"Failed to enqueue user input: {e}")


async def main():
    start_time = datetime.now()
    console.rule("[bold #D97757]Personal Assistant Agent[/]")
    logger.info("🚀 Starting Agent")

    try:
        def get_langchain_tools(server) -> list[StructuredTool]:
            return server.list_tools()

        communication_tools = get_langchain_tools(communication_server)
        logger.info(f"📧 Communication Tools: {len(communication_tools)}")

        planning_tools = get_langchain_tools(planning_server)
        logger.info(f"✅ Planning Tools: {len(planning_tools)}")

        content_tools = get_langchain_tools(content_server)
        logger.info(f"📺 Content Tools: {len(content_tools)}")

        tool_sets = {
            "communication": communication_tools,
            "planning": planning_tools,
            "content": content_tools,
        }

        CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(CHECKPOINT_DB)) as connection:
            checkpointer = AsyncSqliteSaver(connection)
            graph = build_graph(tool_sets, checkpointer)

            config = {
                "configurable": {
                    "thread_id": DEFAULT_THREAD_ID,
                }
            }

            agent_state = {"last_interaction": 0}

            event_queue = asyncio.Queue()
            loop = asyncio.get_running_loop()
            turn_ready = threading.Event()

            threading.Thread(
                target=keyword_listener,
                args=(event_queue, loop, agent_state, turn_ready),
                daemon=True,
            ).start()

            console.print("[dim]Type your message below. Type 'exit' to quit or 'clear' to reset screen.[/dim]")
            turn_ready.set()

            state = {"messages": []}

            while True:
                _, query = await event_queue.get()

                agent_state["last_interaction"] = time.time()

                if query.lower() in ["exit", "quit", "bye", "/exit", "/quit"]:
                    console.print("\n[dim]👋 Goodbye![/dim]\n")
                    break

                if query.lower() in ["clear", "/clear", "cls"]:
                    console.clear()
                    console.rule("[bold #D97757]Personal Assistant Agent[/]")
                    turn_ready.set()
                    continue

                request_counter.start_turn(query)
                snapshot = await graph.aget_state(config)
                current_agent = "supervisor"
                if snapshot and snapshot.values:
                    current_agent = snapshot.values.get("current_agent", "supervisor")

                context_key = AGENT_MESSAGE_KEY.get(
                    current_agent, "supervisor_messages"
                )
                human_message = HumanMessage(content=query)

                new_input = {
                    "messages": [human_message],
                    context_key: [human_message],
                }

                with console.status("[bold #D97757]Thinking...[/]", spinner="dots"):
                    state = await graph.ainvoke(new_input, config=config)
                request_counter.end_turn()

                active_agent = state.get("current_agent", current_agent)
                response_key = AGENT_MESSAGE_KEY.get(
                    active_agent, "supervisor_messages"
                )

                messages = state.get(response_key) or state.get("messages", [])
                last_msg = messages[-1] if messages else None

                if isinstance(last_msg, AIMessage) and last_msg.content:
                    final_response = last_msg.content
                    console.print()
                    console.print(
                        Panel(
                            Markdown(final_response),
                            title="[bold #D97757]Assistant[/]",
                            border_style="#D97757",
                            padding=(1, 2),
                        )
                    )
                    agent_state["last_interaction"] = time.time()

                turn_ready.set()

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            console.print()
            console.print(
                Panel(
                    f"• LLM requests: [cyan]{request_counter.session_total()}[/]\n"
                    f"• Messages: [cyan]{len(state['messages'])}[/]\n"
                    f"• Elapsed Time: [cyan]{execution_time:.2f}s[/]",
                    title="[bold]Session Complete[/bold]",
                    border_style="dim",
                    padding=(0, 2),
                )
            )

    except Exception as e:
        logger.exception(f"❌ An error occurred: {e}")
        raise e


if __name__ == "__main__":
    asyncio.run(main())
