---
title: Restaurant Ordering Agent
description: A multi-turn conversational agent prototype for restaurant ordering, built with Microsoft Agent Framework
ms.date: 2026-03-11
---

## Overview

This prototype demonstrates a multi-turn restaurant ordering chatbot using the
[Microsoft Agent Framework](https://github.com/microsoft/agent-framework) `WorkflowBuilder`.
It routes customer messages through intent classification, order management, and
brand-personalized response generation with real-time streaming output. OpenTelemetry
instrumentation provides visibility into agent internals, including LLM calls,
token usage, intent routing, and workflow execution.

## Architecture

```text
User Input → route_intent → [greeting    → greet           → Output]
                            [order       → update_order → respond → Output]
                            [conversation → skip_order_update → respond → Output]
                            [fallback    → on_error         → Output]
```

The workflow uses conditional edges to branch based on detected intent:

- Greetings bypass LLM classification entirely for fast responses
- Order intents pass through order extraction before responding
- Conversation intents skip order updates and respond directly
- Unmatched intents hit the error fallback

### Components

| File                     | Purpose                                          |
|--------------------------|--------------------------------------------------|
| `workflow_conditional.py` | Workflow orchestrator, CLI, DevUI, and OTel entry points |
| `classification_flow.py`  | Intent classifier (order vs. conversation)        |
| `order_flow.py`           | Order extraction and update agent                 |
| `conversation_flow.py`    | Attendant response generation with streaming      |
| `brand_personality.py`    | Brand voice registry and customer persona loader  |
| `schemas.py`              | Product code, topping, and item data models       |
| `brand_configs.json`      | Brand personality profiles                        |

## Features

- Multi-turn conversation with persistent order state
- Intent-based routing (order, conversation, greeting)
- Streaming token-by-token responses in CLI mode
- Configurable brand personalities (Contoso)
- Customer style adaptation (formal, casual, Gen Z)
- DevUI graph visualization for workflow debugging
- OpenTelemetry tracing with a custom span exporter for agent context
- Robust multi-tier LLM output parsing with fallbacks

## Prerequisites

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/) package manager
- An OpenAI API key (or Azure OpenAI / GitHub Models endpoint)

## Setup

1. Clone the repository and navigate to the project directory.

2. Create a `.env` file with your API credentials:

   ```env
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-5-mini
   ```

   For Azure OpenAI, uncomment the Azure section in `build_client()` and set:

   ```env
   API_HOST=azure
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
   AZURE_OPENAI_CHAT_DEPLOYMENT=your-deployment-name
   ```

3. Install dependencies:

   ```bash
   uv sync
   ```

## Usage

### CLI Mode

Run the interactive command-line interface with streaming output:

```bash
uv run .\workflow_conditional.py
```

The agent greets you automatically on startup. Select a brand (Select 1) and customer style,
then type messages to place orders or ask questions. Type `exit` to quit.

### DevUI Mode

Launch the visual workflow debugger in your browser:

```bash
uv run .\workflow_conditional.py --devui
```

This opens a web interface at `http://localhost:8094` where you can send messages
and see the workflow graph execution in real time.

### OTel Tracing Mode

Enable OpenTelemetry instrumentation to inspect agent internals during a CLI session:

```bash
uv run .\workflow_conditional.py --otel
```

This activates a custom `AgentContextExporter` that filters and prints relevant
span data after each workflow turn. The exporter surfaces:

- LLM call attributes (model, operation, finish reasons)
- Token usage (input and output token counts per call)
- Agent and executor identification (agent name, executor ID, workflow name)
- Tool call metadata (tool name, call ID, arguments, results)
- Message events (system, user, assistant, and tool messages when available)

Combine with the built-in console exporter for full unfiltered span output:

```env
ENABLE_CONSOLE_EXPORTERS=true
```

Or export to an OTLP collector (Jaeger, Aspire Dashboard):

```env
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

## Project Structure

```text
├── workflow_conditional.py   # Main entry point and workflow definition
├── classification_flow.py    # Intent classification agent
├── conversation_flow.py      # Response generation with streaming
├── order_flow.py             # Order extraction and update agent
├── brand_personality.py      # Brand registry and customer style loader
├── schemas.py                # Product and order data models
├── brand_configs.json        # Brand personality configurations
├── casual.txt                # Casual customer style prompt
├── genZ.txt                  # Gen Z customer style prompt
├── pyproject.toml            # Project metadata and dependencies
└── prompts/
    ├── menu.txt              # Restaurant menu definition
    └── menu_with_codes.txt   # Menu with product codes
```

## Configuration

### Brand Personalities

Edit `brand_configs.json` to add or modify brand profiles. Each profile includes
tone, style, key phrases, and core values that shape the agent's responses.

### Customer Styles

Three customer interaction styles are available:

| Style  | Description                        | Source       |
|--------|------------------------------------|--------------|
| Formal | Professional and polite tone       | Built-in     |
| Casual | Relaxed, buddy-like conversation   | `casual.txt` |
| Gen Z  | TikTok-style slang and energy      | `genZ.txt`   |
