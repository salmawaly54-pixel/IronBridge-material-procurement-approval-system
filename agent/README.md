# agent/

Two entry points, both talking to `mcp_server/server.py` through the
real MCP protocol (no direct Python imports of the server):

## `agent.py` -- interactive, Groq-driven

The genuine agent: it discovers whatever tools the server currently
exposes, hands them to Groq's model (`llama-3.3-70b-versatile`) as
real tool-use tools, and lets the model decide which to call and with
what arguments. Nothing in this file hard-codes which tool answers
which question.

Groq (https://console.groq.com) was chosen over a paid API for this
project: OpenAI-compatible tool calling, genuine free tier, no credit
card required.

```bash
export GROQ_API_KEY=gsk_...
python3 agent/agent.py
# or, against a deployed HTTP server:
python3 agent/agent.py --transport http --http-url http://host:8080/mcp --http-token secret
```

Try:
- "What steel do we have in stock?"
- "Submit a request for 15 units of steel (material 2) for project 2, I'm employee 7"
- "Log me in as Sami with PIN 1108" -- watch the tool set change live
- "Approve request 8" -- answer the real confirmation prompt yourself

## `demo_scenario.py` -- fixed, repeatable script (no LLM)

A deterministic walk-through hitting all 8 protocol concerns with the
same inputs every run -- this is what `demo_transcripts/scripted_demo_run.txt`
was captured from. No API key needed except to see the final
sampling step in `generate_procurement_report` actually complete
(without one, it fails with a clear, correct error instead of a crash
or a hang -- see `mcp_client.make_sampling_callback`).

```bash
python3 agent/demo_scenario.py
```

## `mcp_client.py` -- shared connection logic

Everything client-side-protocol-specific lives here so both entry
points share it instead of re-implementing:

| Concern | Where |
|---|---|
| Capability negotiation | Passing real `sampling_callback`/`elicitation_callback` (not the SDK's stub defaults) is what makes the client *declare* those capabilities in `initialize`. `check_capability()` is the other half -- reading back what the *server* declared before relying on it. |
| Notifications | `make_message_handler` reacts to a real `ToolListChangedNotification`. **Important gotcha we hit and fixed:** the SDK awaits this handler inline inside its own receive loop, so the handler must schedule its reaction (`session.list_tools()`) as a background task via `asyncio.create_task` -- awaiting it directly deadlocks, since the loop that would deliver that response is the one blocked on the handler. |
| Elicitation | `make_elicitation_callback` is a real human-in-the-loop prompt (or, for the deterministic demo, a fixed canned answer) -- never silent auto-accept. |
| Sampling | `make_sampling_callback` calls the Groq API directly from *this* process -- the client's own model, never the server's. |
| Transport | `connect(transport="stdio"|"http", ...)` -- same call shape either way. |

## Requirements

```bash
pip install -r agent/requirements.txt
```

`mcp` is pinned to `1.28.1` -- see the note in the root `requirements.txt`;
the current latest (2.0.0) removed the client-side API this code uses.

## Getting a Groq key

1. Go to https://console.groq.com
2. Sign in (email or Google) -- no credit card, no phone verification
3. **API Keys** -> **Create API Key** -> copy it
4. Put it in `.env` at the repo root: `GROQ_API_KEY=gsk_...`

Free tier: ~30 requests/minute, ~14,400 requests/day per model -- far
more than this project needs.
