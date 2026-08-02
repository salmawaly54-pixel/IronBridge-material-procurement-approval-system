"""
Interactive IronBridge procurement agent.

Unlike demo_scenario.py (a fixed script for repeatable grading), this
is the genuine "someone types a request in plain English" agent: it
discovers whatever tools/resources/prompts the MCP server currently
exposes, hands them to Groq's model as real tool-use tools, and lets
the model decide which ones to call and with what arguments. Nothing
here hard-codes which tool answers which question.

Uses Groq (https://console.groq.com) as the driving model -- an
OpenAI-compatible chat API with genuine free-tier tool calling, no
credit card required. See mcp_client.py's make_sampling_callback for
the model that fulfils the server's own sampling/createMessage calls
(same provider, same key).

Usage:
    export GROQ_API_KEY=...
    python3 agent/agent.py                       # stdio, spawns the server
    python3 agent/agent.py --transport http --http-url http://localhost:8080/mcp --http-token secret

Try, e.g.:
    "What steel do we have in stock?"
    "Submit a request for 15 units of steel (material 2) for project 2, I'm employee 7"
    "Log me in as Sami with PIN 1108"                     -> triggers notifications
    "Approve request <id>"                                -> triggers elicitation (real prompt!)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
import mcp_client

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(REPO_ROOT, ".env"))  # picks up GROQ_API_KEY,
                                                # IRONBRIDGE_MCP_URL, etc. if
                                                # a .env file exists there;
                                                # no-op otherwise.

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are the IronBridge Construction procurement assistant. Use the "
    "available tools to answer questions and carry out requests. Only "
    "call tools that are currently offered to you -- if an action isn't "
    "available yet (e.g. approving a request), explain to the user what "
    "they need to do first (e.g. authenticate) rather than guessing."
)


def mcp_tool_to_groq(tool) -> dict:
    """MCP's Tool shape -> Groq/OpenAI-compatible tool-calling shape."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


async def run_agent(transport: str, http_url: str | None, http_token: str | None):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("GROQ_API_KEY is not set -- the agent's own driving model "
              "(the one deciding which tools to call) needs it. Get a free "
              "key at https://console.groq.com -- sampling requests FROM "
              "the server would also fail without it.")
        return

    from groq import Groq
    groq_client = Groq(api_key=api_key)

    state = {"groq_tools": []}

    async def refresh_tools_and_announce():
        result = await SESSION.list_tools()
        state["groq_tools"] = [mcp_tool_to_groq(t) for t in result.tools]
        names = [t.name for t in result.tools]
        print(f"\n[tool set updated] now available: {names}\n")

    connect_kwargs = dict(
        transport=transport,
        auto_elicit_answers=None,  # genuine interactive elicitation -- real prompts
        on_tools_changed=refresh_tools_and_announce,
    )
    if transport == "stdio":
        connect_kwargs["server_command"] = [sys.executable, "mcp_server/server.py"]
        connect_kwargs["server_cwd"] = REPO_ROOT
    else:
        connect_kwargs["http_url"] = http_url
        connect_kwargs["http_token"] = http_token

    async with mcp_client.connect(**connect_kwargs) as (session, init_result):
        global SESSION
        SESSION = session

        # === CONCERN: Capability negotiation (client side) ===
        print(f"Connected to {init_result.serverInfo.name} v{init_result.serverInfo.version}")
        print(f"Server capabilities: {init_result.capabilities}")
        supports_notifications = mcp_client.check_capability(init_result, "tools.listChanged")
        print(f"Server advertises tools.listChanged: {supports_notifications}")
        if not supports_notifications:
            print("(No push support declared -- this agent would need to "
                  "poll list_tools() periodically instead of trusting a "
                  "notification that may never come. Not implemented here "
                  "since IronBridge's server does declare it.)")

        await refresh_tools_and_announce()

        print(
            "\nIronBridge Procurement Assistant -- type a request in plain "
            "English, or 'quit' to exit.\n"
        )

        conversation: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

        while True:
            user_text = await asyncio.to_thread(input, "you> ")
            if user_text.strip().lower() in ("quit", "exit"):
                break

            conversation.append({"role": "user", "content": user_text})

            # Loop until the model stops asking for tool calls.
            while True:
                response = groq_client.chat.completions.create(
                    model=MODEL,
                    max_tokens=1024,
                    tools=state["groq_tools"],
                    messages=conversation,
                )

                message = response.choices[0].message
                # Groq/OpenAI's assistant message must be echoed back verbatim
                # (including tool_calls) for the follow-up call to make sense.
                # IMPORTANT: the API rejects "tool_calls": null outright (it
                # must be either a real list or the key must be absent) --
                # this bit us on the second turn of a real conversation, once
                # a previous plain-text reply (no tool calls) got sent back
                # as part of the history.
                assistant_msg = {"role": "assistant", "content": message.content}
                if message.tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ]
                conversation.append(assistant_msg)

                if not message.tool_calls:
                    if message.content:
                        print(f"assistant> {message.content}")
                    break

                for tc in message.tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    print(f"  [calling tool] {tc.function.name}({args})")
                    result = await session.call_tool(tc.function.name, args)
                    text = "".join(c.text for c in result.content if hasattr(c, "text"))
                    print(f"  [tool result] {text}")
                    conversation.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": text,
                        }
                    )
                # loop again so the model can react to the tool result(s)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--http-url", default=os.environ.get("IRONBRIDGE_MCP_URL"))
    parser.add_argument("--http-token", default=os.environ.get("IRONBRIDGE_API_TOKEN"))
    args = parser.parse_args()
    asyncio.run(run_agent(args.transport, args.http_url, args.http_token))


if __name__ == "__main__":
    main()
