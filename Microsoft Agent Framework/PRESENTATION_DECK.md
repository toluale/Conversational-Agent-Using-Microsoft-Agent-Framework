<!-- markdownlint-disable-file -->
# Building Multi-Agent Workflows with Microsoft Agent Framework

> **A Technical Presentation**
> Orchestrating Specialized AI Agents for Production Applications

---

## Slide 1: Title

### Building Multi-Agent Workflows with Microsoft Agent Framework

*From Agent Design to Production Deployment*

**Demo:** Multi-turn restaurant ordering chatbot with brand personality

---

## Slide 2: Agenda

1. Introduction & Motivation — Why agent orchestration?
2. Architecture Overview — System design and component map
3. Agent Design Patterns — Defining specialized agents
4. Workflow Orchestration — WorkflowBuilder, routing, and graph construction
5. State Management & Data Flow — Context passing and inter-agent communication
6. Brand Personality & Prompt Engineering — Dynamic persona injection
7. Observability & Debugging — OpenTelemetry, DevUI, and Aspire Dashboard
8. Deployment & Production — Docker, Azure Container Apps, Microsoft Foundry
9. Why Microsoft Agent Framework? — Comparison with LangChain/LangGraph

---

## Section 1: Introduction & Motivation

---

## Slide 3: The Problem — Why Single Agents Are Not Enough

**Single-agent limitations:**

- **Token limits** — One agent cannot hold the full context of a complex conversation (menu, order state, history, brand voice, tools) without exceeding context windows
- **Task specialization vs generalization** — An agent optimized for intent classification produces poor free-form responses; a conversational agent is unreliable at structured data extraction
- **Error isolation** — When one monolithic agent fails, the entire interaction fails; no ability to retry or reroute a specific sub-task
- **Prompt bloat** — Instructions for classification + order management + response generation + brand personality in one prompt degrades performance

> **Key insight:** Just as microservices decompose monolithic backends, **multi-agent orchestration** decomposes monolithic AI agents into specialized, composable units.

---

## Slide 4: What is Agent Orchestration?

**Definition:** Coordinating multiple specialized AI agents to collaboratively handle complex tasks, with each agent responsible for a specific capability.

**Analogy: The Restaurant Kitchen**

| Kitchen Station | Agent Equivalent | Responsibility |
|---|---|---|
| Host / Maître d' | OrderIntentClassifier | Routes incoming requests |
| Line Cook | OrderUpdateAgent | Processes specific tasks (order extraction) |
| Server | RestaurantAttendant | Interacts with the customer |

**Key orchestration concepts:**

- **Routing** — Directing messages to the right agent based on intent
- **State passing** — Sharing context (order, history) between agents
- **Structured output** — Enforcing schema compliance for reliable inter-agent data

---

## Slide 5: The Demo Application

**What we built:** A multi-turn restaurant ordering chatbot

- **Three specialized agents** working together via a workflow graph
- **Four restaurant brands** with distinct personalities (Contoso, Domino's, P.F. Chang's, Chipotle)
- **Three customer personas** (Formal, Casual, Gen Z)
- **Real-time streaming** responses with token-by-token output
- **Full observability** via OpenTelemetry and DevUI

```bash
# Run the demo
uv run ./workflow_conditional.py
```

### 🎬 LIVE DEMO 1: The Running Application

> Place a simple order and watch the agents collaborate in real-time.

---

## Section 2: Architecture Overview

---

## Slide 6: System Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                        WorkflowBuilder                          │
│                                                                 │
│  ┌──────────────┐     ┌────────────────┐     ┌──────────────┐  │
│  │ route_intent  │────▶│  update_order   │────▶│   respond    │  │
│  │ (Classifier)  │     │ (OrderUpdate)  │     │ (Attendant)  │  │
│  └──────────────┘     └────────────────┘     └──────────────┘  │
│       │ Case:order              ▲                    ▲          │
│       │                         │                    │          │
│       │ Case:conversation       │                    │          │
│       ├─────────────▶ ┌─────────────────┐───────────┘          │
│       │               │skip_order_update│                       │
│       │               └─────────────────┘                       │
│       │                                                         │
│       │ Case:greeting                                           │
│       ├─────────────▶ ┌──────────┐                              │
│       │               │  greet   │                              │
│       │               └──────────┘                              │
│       │                                                         │
│       │ Default                                                 │
│       └─────────────▶ ┌──────────┐                              │
│                       │ on_error │                              │
│                       └──────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

**Flow:** User Input → Intent Classification → Conditional Routing → Processing → Streaming Response

---

## Slide 7: The Agent Trio

| Agent | File | Type | Tools | Output |
|---|---|---|---|---|
| **OrderIntentClassifier** | `classification_flow.py` | Classification | None | `IntentDecision` (structured) |
| **OrderUpdateAgent** | `order_flow.py` | Data Extraction | `get_menu`, `get_menu_with_codes` | `OrderUpdate` (structured) |
| **RestaurantAttendant** | `conversation_flow.py` | Conversation | `get_menu`, `confirm_order` | Free text (streaming) |

**Design principle:** Each agent has a **single responsibility** with minimal overlap. The classifier has no tools (pure routing), the order agent has data tools (extraction), and the conversation agent has interaction tools (streaming, confirmation).

---

## Slide 8: Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Agent Framework | `agent-framework-core` | Agent/workflow SDK |
| LLM Provider | Azure OpenAI | GPT inference |
| Data Validation | Pydantic | Structured output, schemas |
| Observability | OpenTelemetry | Tracing, metrics |
| Visual Debugging | `agent-framework-devui` | Workflow visualization |
| Cloud Deployment | Azure Container Apps | Production hosting |
| Authentication | `azure-identity` | Managed identity / API key |

---

## Slide 9: LLM Client Configuration

```python
# workflow_conditional.py — build_client()

def build_client() -> AzureOpenAIChatClient:
    endpoint = _normalize_azure_endpoint(_require_env("AZURE_OPENAI_ENDPOINT"))
    deployment = _require_env("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")

    # Prefer API key auth when provided
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    if api_key:
        return AzureOpenAIChatClient(
            endpoint=endpoint, api_key=api_key, deployment_name=deployment,
        )

    # Fall back to Entra ID / Managed Identity
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAIChatClient(
        endpoint=endpoint, credential=token_provider, deployment_name=deployment,
    )
```

**Key points:**
- Endpoint normalization strips `/openai` suffix for consistency
- Dual auth: API key for local dev, `DefaultAzureCredential` for production
- Single function centralizes client construction

---

## Section 3: Agent Design Patterns

---

## Slide 10: Defining Agents with the SDK

```python
# classification_flow.py — Agent with structured output, no tools

agent = Agent(
    client=client,
    name="OrderIntentClassifier",
    instructions=(
        "Classify the latest customer message for a restaurant assistant. "
        "Return intent='order' when the customer is adding/removing/changing items. "
        "Return intent='conversation' for greetings, menu questions, or small talk. "
        "Always include a short reason string explaining the classification."
    ),
    response_format=IntentDecision,  # ← Pydantic model for structured output
)
```

**The `Agent` constructor is the single API for all agent types:**

| Parameter | Purpose | Example |
|---|---|---|
| `client` | LLM client | `AzureOpenAIChatClient` |
| `name` | Agent identifier | `"OrderIntentClassifier"` |
| `instructions` | System prompt | Inline string |
| `response_format` | Structured output schema | Pydantic `BaseModel` |
| `tools` | Agent capabilities | `[get_menu, confirm_order]` |

### 🎬 LIVE DEMO 2: Agent Design

> Walk through the Agent() constructor in classification_flow.py

---

## Slide 11: Structured Output Agents

**The Problem:** LLMs return free-form text. You need reliable, parseable data.

**The Solution:** `response_format=PydanticModel` — first-class structured output.

```python
# classification_flow.py — Structured output model

class IntentDecision(BaseModel):
    intent: Literal["order", "conversation"]
    reason: str = ""

# order_flow.py — Nested structured output

class OrderItem(BaseModel):
    name: str
    quantity: int = 1
    size: str | None = None
    options: list[str] = Field(default_factory=list)
    notes: str | None = None

class OrderUpdate(BaseModel):
    order: LLMOrder        # Contains list[OrderItem]
    summary: str = ""
```

**Multi-tier fallback parsing for robustness:**

```python
# 1. Strict JSON → Pydantic validation
result = IntentDecision.model_validate_json(response.text)

# 2. Regex key-value extraction (handles format drift)
intent_match = re.search(r"intent\s*[:=]\s*['\"]?(order|conversation)['\"]?", text)

# 3. Raw dict parsing (last resort)
parsed = json.loads(text)
```

---

## Slide 12: Tool-Equipped Agents

```python
# conversation_flow.py — @tool decorator

@tool
def get_menu(
    category: Annotated[str, "Menu category: 'burgers', 'fries', or 'drinks'"] = "",
) -> str:
    """Retrieve the restaurant menu."""
    menu_path = Path(__file__).parent / "prompts" / "menu.txt"
    text = menu_path.read_text(encoding="utf-8")
    if category:
        sections = text.split("## ")
        for section in sections:
            if section.strip().lower().startswith(category.strip().lower()):
                return f"## {section.strip()}"
    return text

@tool
def confirm_order(**kwargs) -> str:
    """Produce a checkout summary for the current order."""
    order = kwargs.get("current_order", {})
    items = order.get("items", [])
    # ... generates formatted order summary
```

**Key pattern:** Tools provide agents with capabilities beyond text generation. The `@tool` decorator converts any Python function into an agent tool with auto-generated JSON schema from type hints.

---

## Slide 13: Streaming Agents

```python
# conversation_flow.py — Streaming response generation

async for update in conversation_flow.stream_respond(
    chat_history=chat_history,
    current_order=current_order,
    brand_instructions=brand_instructions,
    customer_style_instructions=customer_style_instructions,
    order_summary=order_summary,
):
    chunk = update.text
    if chunk:
        sys.stdout.write(chunk)  # Token-by-token output

# Under the hood:
response = await self._agent.run(json.dumps(payload), stream=True)
async for update in response:
    yield update  # AgentResponseUpdate chunks
```

**Why streaming matters:**
- Responsive user experience (no waiting for full response)
- Real-time feedback in CLI and DevUI
- Tool calls appear as they happen (function_call → function_result)

---

## Slide 14: Product Code / SKU System

```python
# schemas.py — Discriminated union pattern for LLM output validation

class LLMTopping(BaseModel):
    name: str
    amount: Optional[str] = "normal"

class LLMBurgerItem(BaseModel):
    name: str                                          # e.g., "Classic Burger"
    toppings: Optional[list[LLMTopping]] = None         # Auto-fills defaults
    size: Optional[str] = "quarter lb"                  # "quarter lb", "half lb"
    bun: Optional[str] = "sesame"                       # "sesame", "pretzel"
    patties: Optional[str] = "single"                   # "single", "double"
    cook: Optional[str] = "normal"                      # "normal", "well-done"
    quantity: Optional[int] = 1

class LLMFriesItem(BaseModel): ...
class LLMDrinkItem(BaseModel): ...

# Discriminated union: routes to correct model based on item name
def item_discriminator(v: Any) -> str:
    name = v.get("name", "").lower() if isinstance(v, dict) else ""
    if "burger" in name: return "burger"
    if "fries" in name: return "fries"
    return "drink"

LLMItem = Annotated[
    LLMBurgerItem | LLMFriesItem | LLMDrinkItem,
    Discriminator(item_discriminator),
]
```

**Validation pipeline:** LLM output → Pydantic model → validated Order object

---

## Section 4: Workflow Orchestration

---

## Slide 15: WorkflowBuilder — Declarative Graph Construction

```python
# workflow_conditional.py — The complete workflow graph

workflow = (
    WorkflowBuilder(start_executor=route_intent, max_iterations=8)
    .add_switch_case_edge_group(
        route_intent,
        [
            Case(condition=_is_greeting, target=greet),
            Case(condition=_is_order, target=update_order),
            Case(condition=_is_conversation, target=skip_order_update),
            Default(target=on_error),
        ],
    )
    .add_edge(update_order, respond)
    .add_edge(skip_order_update, respond)
    .build()
)
```

**Key WorkflowBuilder concepts:**

| Method | Purpose |
|---|---|
| `WorkflowBuilder(start_executor=...)` | Set the entry point |
| `.add_switch_case_edge_group()` | Conditional routing with Case/Default |
| `.add_edge(source, target)` | Sequential chaining |
| `.build()` | Validate and compile the immutable workflow |

### 🎬 LIVE DEMO 3: Workflow Graph

> Run `uv run ./workflow_conditional.py --devui` and view the visual workflow graph in the browser.

---

## Slide 16: The @executor Decorator

```python
# workflow_conditional.py — Executor nodes are async functions

@executor(id="route_intent")
async def route_intent(user_message: str, ctx: WorkflowContext[str, dict]) -> None:
    # Classify intent and route via envelope
    decision = await intent_flow.classify(chat_history, current_order)
    envelope = {"intent": decision.intent, "chat_history": chat_history, ...}
    await ctx.send_message(json.dumps(envelope))

@executor(id="update_order")
async def update_order(envelope_json: str, ctx: WorkflowContext[str, dict]) -> None:
    # Extract order data from conversation
    update = await order_flow.update_order(envelope["chat_history"], envelope["current_order"])
    ...

@executor(id="respond")
async def respond(envelope_json: str, ctx: WorkflowContext[str, dict]) -> None:
    # Generate streaming response with brand personality
    async for update in conversation_flow.stream_respond(...):
        ...
```

**Five executors in the workflow:**

| Executor | Role |
|---|---|
| `route_intent` | Entry point: classifies intent, emits envelope |
| `update_order` | Runs OrderFlow to update order items |
| `skip_order_update` | Pass-through for non-order messages |
| `respond` | Generates streamed attendant response |
| `greet` | Handles greeting messages with simplified context |
| `on_error` | Fallback error handler |

---

## Slide 17: Conditional Routing with Case/Default

```python
# Predicate functions determine routing
def _is_order(envelope: Any) -> bool:
    if isinstance(envelope, dict):
        return envelope.get("intent") == "order"
    if isinstance(envelope, str):
        parsed = json.loads(envelope)
        return parsed.get("intent") == "order"
    return False

def _is_conversation(envelope: Any) -> bool:
    ...  # Same pattern, checks intent == "conversation"

def _is_greeting(envelope: Any) -> bool:
    ...  # Checks intent == "greeting"
```

**The routing pattern:**

```text
route_intent output: {"intent": "order", ...}
    → _is_order(envelope) returns True
    → routes to update_order executor

route_intent output: {"intent": "conversation", ...}
    → _is_conversation(envelope) returns True
    → routes to skip_order_update executor

No predicate matches:
    → Default routes to on_error
```

---

## Slide 18: Greeting Short-Circuit Pattern

```python
# Optimization: bypass LLM classification for trivial intents

_GREETING_WORDS = {
    "hello", "hi", "hey", "greetings", "howdy", "hola",
    "good morning", "good afternoon", "good evening"
}

# In route_intent executor:
if message.lower().strip("!.,? ") in _GREETING_WORDS:
    intent = "greeting"          # ← No LLM call needed
    reason = "Customer greeting detected"
else:
    decision = await intent_flow.classify(chat_history, current_order)
    intent = decision.intent     # ← LLM classification
    reason = decision.reason
```

**Why this matters:**
- Avoids unnecessary LLM API calls (cost + latency)
- Greetings are deterministic — no need for AI classification
- Pattern: **use code when you can, use AI when you must**

---

## Slide 19: Fan-In Pattern

```text
Two branches converge on a single response generator:

         ┌── update_order ──────┐
route_intent                     ├──▶ respond
         └── skip_order_update ──┘
```

```python
# Sequential edges create the fan-in
.add_edge(update_order, respond)
.add_edge(skip_order_update, respond)
```

Whether the message triggered an order update or not, the response generator runs with the current state. Same downstream processing, different upstream paths.

---

## Section 5: State Management & Data Flow

---

## Slide 20: WorkflowContext State API

```python
# Typed state management within workflow executors

# Read state
chat_history = ctx.get_state("chat_history", [])
current_order = ctx.get_state("current_order", {"items": []})

# Write state
ctx.set_state("chat_history", updated_history)
ctx.set_state("current_order", updated_order)
```

**Five state keys tracked across the workflow:**

| Key | Type | Purpose |
|---|---|---|
| `chat_history` | `list[dict]` | Conversation messages |
| `current_order` | `dict` | Order items and structure |
| `last_intent` | `str` | Most recent classification |
| `last_intent_reason` | `str` | Classifier explanation |
| `order_summary` | `str` | Order summary from extraction |

---

## Slide 21: Envelope-Based Message Passing

```python
# JSON-serialized envelope between executors via ctx.send_message()

envelope = {
    "chat_history": chat_history,        # Full conversation context
    "current_order": current_order,       # Current order state
    "brand_name": brand_name,             # Active restaurant brand
    "customer_style": customer_style,     # Customer persona mode
    "intent": intent,                     # Classification result
    "intent_reason": reason,              # Classification explanation
}
await ctx.send_message(json.dumps(envelope, ensure_ascii=True))
```

**Why envelope-based passing?**
- **Clean serialization boundary** — each executor receives self-contained context
- **Explicit data flow** — no hidden state mutations between nodes
- **Debuggable** — envelope contents visible in DevUI and OTel traces

---

## Slide 22: Persistent Session State

```python
# Dual-write pattern: workflow context + persistent fallback store

_PERSISTENT_SESSION_STATE: dict[str, Any] = {
    "chat_history": [],
    "current_order": {"items": []},
    "last_intent": "",
    "last_intent_reason": "",
    "order_summary": "",
}

def _save_session_state(ctx, state):
    # Write to workflow context
    ctx.set_state("chat_history", state["chat_history"])
    ctx.set_state("current_order", state["current_order"])
    ...
    # Also write to persistent fallback
    _PERSISTENT_SESSION_STATE["chat_history"] = state["chat_history"]
    _PERSISTENT_SESSION_STATE["current_order"] = state["current_order"]
    ...
```

**Motivation:** Workflow context state may not survive between DevUI reloads. The dual-write pattern ensures state persistence across interaction modes.

---

## Section 6: Brand Personality & Prompt Engineering

---

## Slide 23: Brand Personality Registry

```python
# brand_personality.py — Pydantic-powered brand profiles

class BrandProfile(BaseModel):
    name: str
    tone: str
    style: str
    key_phrases: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)

class BrandPersonalityRegistry:
    def __init__(self):
        self._profiles = self._load_profiles()  # From brand_configs.json

    def get_brand_instructions(self, brand_name: str) -> str:
        profile = self.get_brand(brand_name)
        return (
            f"Represent {profile.name}.\n"
            f"Tone: {profile.tone}.\n"
            f"Style: {profile.style}.\n"
            f"Key phrases to use naturally: {', '.join(profile.key_phrases)}.\n"
            f"Core values to reflect: {', '.join(profile.values)}."
        )
```

---

## Slide 24: Four Restaurant Brand Profiles

| Brand | Tone | Key Phrases | Values |
|---|---|---|---|
| **Contoso Restaurant** | Warm and welcoming | delicious, home-style, fresh, made with love | Quality, community, comfort |
| **Domino's Pizza** | Fast, friendly, tech-savvy | hot and fresh, delivered in 30 minutes | Speed, innovation, reliability |
| **P.F. Chang's** | Elegant, modern, culturally rich | wok-fired, crafted with care, bold flavors | Authenticity, culinary excellence |
| **Chipotle** | Fresh, bold, socially conscious | real ingredients, responsibly sourced, build your own | Sustainability, transparency |

### 🎬 LIVE DEMO 4: Brand Personality Switch

> Same order ("I'd like a cheeseburger with fries") placed to Contoso vs Domino's vs Chipotle. Watch how brand voice transforms the response.

---

## Slide 25: Customer Style Personas

**Three persona modes that adapt the attendant's communication style:**

| Style | Source | Tone |
|---|---|---|
| **Formal** | Built-in | Professional, polite, structured |
| **Casual** | `casual.txt` | "Keep it chill and real, like you're talking to a buddy" |
| **Gen Z** | `genZ.txt` | "Talk like you're on TikTok — use Gen Z slang, keep it hype" |

**Dynamic prompt composition:**

```text
brand_voice (from brand_configs.json)
    + customer_persona (from persona files)
        + order_context (current order state)
            + chat_history (conversation history)
                = Complete agent context
```

**Key principle:** Personality is injected into response agents at runtime, keeping the agent definition clean and the brand voice data-driven.

---

## Section 7: Observability & Debugging

---

## Slide 26: OpenTelemetry Integration

```python
# workflow_conditional.py — One-line instrumentation setup

from agent_framework.observability import (
    configure_otel_providers, create_resource, enable_instrumentation
)

# Set up OTel with custom exporter
configure_otel_providers(
    enable_sensitive_data=True,
    exporters=[AgentContextExporter()]
)
enable_instrumentation(enable_sensitive_data=True)
```

**Attributes automatically tracked:**

| Attribute | Example |
|---|---|
| `gen_ai.agent.name` | "OrderIntentClassifier" |
| `gen_ai.request.model` | "gpt-4o" |
| `gen_ai.usage.input_tokens` | 1,247 |
| `gen_ai.usage.output_tokens` | 89 |
| `gen_ai.tool.name` | "get_menu" |
| `gen_ai.tool.call.arguments` | `{"category": "burgers"}` |
| `executor.id` | "route_intent" |
| `workflow.name` | "restaurant-ordering" |

---

## Slide 27: Custom Span Exporter

```python
# workflow_conditional.py — Filter relevant agent spans from noise

class AgentContextExporter(SpanExporter):
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            attrs = {k: v for k, v in span.attributes.items()
                     if k in _RELEVANT_ATTRIBUTES}
            events = [
                {"event": e.name, "data": dict(e.attributes)}
                for e in span.events if e.name in _RELEVANT_EVENT_NAMES
            ]
            if attrs or events:
                print(json.dumps({"span": span.name, "attributes": attrs,
                                   "events": events}, indent=2))
        return SpanExportResult.SUCCESS
```

**Relevant events tracked:**
- `gen_ai.system.message` — System prompts sent to the LLM
- `gen_ai.user.message` — User inputs
- `gen_ai.assistant.message` — LLM responses
- `gen_ai.tool.message` — Tool call results
- `gen_ai.choice` — Model selection reasoning

---

## Slide 28: Azure Monitor / Application Insights

```python
# Dual-mode telemetry: Azure Monitor when available, local otherwise

connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

if connection_string:
    # Production: Azure Monitor with live metrics
    configure_azure_monitor(
        connection_string=connection_string,
        resource=create_resource("restaurant-ordering-agent"),
        enable_live_metrics=True,
    )
else:
    # Development: Local OTel exporters
    configure_otel_providers(
        enable_sensitive_data=True,
        exporters=[AgentContextExporter()]
    )
```

**Production consideration:** Set `enable_sensitive_data=False` in production to prevent logging full prompt content and tool arguments.

---

## Slide 29: DevUI — Visual Workflow Debugger

```python
# One line to launch visual debugging
from agent_framework.devui import serve
serve(entities=[workflow], port=8094, auto_open=True, instrumentation_enabled=True)
```

**DevUI features:**
- 🔍 **Workflow graph visualization** — See your executor graph rendered in the browser
- 💬 **Conversation interface** — Chat with your agent directly in the UI
- 📊 **Event inspector** — Streaming events, tool calls, and state changes in real-time
- 🔬 **Trace viewer** — OpenTelemetry spans with token usage per message
- 🚀 **One-click deployment** — Deploy to Azure Container Apps from the UI

### 🎬 LIVE DEMO 5: Observability

> Run `uv run ./workflow_conditional.py --otel` and examine agent spans, token usage, and tool calls.

---

## Slide 30: Aspire Dashboard

```yaml
# docker-compose.aspire-dashboard.yml

services:
  aspire-dashboard:
    image: mcr.microsoft.com/dotnet/aspire-dashboard:9.0
    ports:
      - "18888:18888"    # Dashboard UI
      - "4317:18889"     # OTLP gRPC
      - "4318:18890"     # OTLP HTTP
    environment:
      DOTNET_DASHBOARD_UNSECURED_ALLOW_ANONYMOUS: "true"
```

**Usage:**

```bash
docker compose -f docker-compose.aspire-dashboard.yml up -d
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
uv run ./workflow_conditional.py --otel
# Open http://localhost:18888 to view traces
```

The Aspire Dashboard provides a visual trace explorer showing the full execution flow: agent calls, tool invocations, token usage, and timing information.

---

## Section 8: Deployment & Production

---

## Slide 31: Local Development Modes

```bash
# CLI mode — Interactive chat with streaming output
uv run ./workflow_conditional.py

# OTel mode — CLI + OpenTelemetry tracing
uv run ./workflow_conditional.py --otel

# DevUI mode — Web-based visual debugger at :8094
uv run ./workflow_conditional.py --devui
```

**Development workflow:**
1. Build and iterate in CLI mode
2. Debug with DevUI for visual workflow inspection
3. Profile with OTel mode for token usage and latency analysis
4. Deploy when ready

---

## Slide 32: Docker Containerization

```dockerfile
# Dockerfile — Production-ready container

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git && rm -rf /var/lib/apt/lists/*

# Install uv and dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv

COPY . .
RUN uv sync --frozen

EXPOSE 80
ENV PORT=80

CMD ["uv", "run", "python", "workflow_conditional.py"]
```

---

## Slide 33: Azure Container Apps Deployment

```yaml
# azure.yaml — azd configuration
name: agent-framework-demo
metadata:
  template: azd-init@1.23.10
services:
  agent-framework:
    project: .
    host: containerapp
    language: python
    docker:
      path: ./Dockerfile
      context: .
resources:
  agent-framework:
    type: host.containerapp
    port: 80
```

```yaml
# agent.yaml — Container resource configuration
name: agent-framework
dockerfile_path: Dockerfile
resources:
  cpu: '0.5'
  memory: 1.0Gi
```

**Deployment commands:**

```bash
azd package --all    # Build container images
azd up               # Deploy to Azure Container Apps
```

---

## Slide 34: Microsoft Foundry Hosted Agent

**Steps to deploy as a Foundry hosted agent:**

1. **Build and push** the container image to Azure Container Registry (ACR)
2. **Create hosted agent** in the AI Foundry portal
3. **Configure environment variables** (API_HOST, endpoint, deployment name)
4. **Start the container runtime**
5. **Smoke test** via the Foundry Playground

**Production resource sizing:**

| Resource | Value |
|---|---|
| CPU | 0.5 cores |
| Memory | 1.0 GiB |
| Port | 80 |

---

## Section 9: Why Microsoft Agent Framework?

### Comparison with LangChain / LangGraph

---

## Slide 35: The Framework Landscape

| | Microsoft Agent Framework | LangChain | LangGraph |
|---|---|---|---|
| **Mental model** | Directed graph of typed executors | Linear pipeline of runnables | State machine with shared state |
| **Built for** | Multi-agent orchestration | RAG, chains, general AI | Stateful agent workflows |
| **Primary API** | `WorkflowBuilder` + `Agent` | LCEL pipe `\|` operator | `StateGraph` |
| **Validation** | Build-time graph validation | Runtime only | Compile-time graph |
| **Visual debugging** | DevUI (built-in, free) | LangSmith (paid SaaS) | LangSmith (paid SaaS) |
| **Multi-language** | Python + .NET | Python + JS/TS | Python + JS/TS |

---

## Slide 36: Differentiator #1 — DevUI Visual Debugger

**No built-in free equivalent in LangChain/LangGraph.**

```python
# MAF: One line launches a full development environment
from agent_framework.devui import serve
serve(entities=[workflow])
```

**DevUI gives you:**
- Visual workflow graph — see executor connections and active nodes
- Conversation interface — chat with your agent in the browser
- Event inspector — real-time streaming events, tool calls, state changes
- Trace viewer — OpenTelemetry spans with per-message token usage
- One-click deployment — deploy to Azure Container Apps from the UI

**LangChain alternative:** LangSmith — a separate paid SaaS product that requires sending data to an external cloud service. DevUI runs locally, free, with zero external dependencies.

---

## Slide 37: Differentiator #2 — Structured Output, Not Bolted On

```python
# MAF — response_format is a first-class constructor parameter
agent = Agent(
    client=client,
    name="OrderIntentClassifier",
    instructions="Classify intent...",
    response_format=IntentDecision,  # ← That's it. Native. Clean.
)
response = await agent.run(message)
result = IntentDecision.model_validate_json(response.text)
```

```python
# LangChain — structured output requires method chaining
llm = AzureChatOpenAI(...)
structured_llm = llm.with_structured_output(IntentDecision)
result = structured_llm.invoke(message)
```

MAF treats structured output as a **core capability**, not an add-on method. The Pydantic model goes directly in the Agent constructor — no separate parser chains, no `.with_structured_output()` wrapper.

---

## Slide 38: Differentiator #3 — Explicit Message Passing

```python
# MAF — Directed messages between executors
@executor(id="route_intent")
async def route_intent(user_msg: str, ctx: WorkflowContext) -> None:
    ctx.set_state("chat_history", updated_history)
    await ctx.send_message(json.dumps(envelope))  # ← Explicit, typed, directed

# LangGraph — Shared mutable state
def route_intent(state: AgentState) -> dict:
    return {"intent": "order", "messages": [new_msg]}  # ← Mutates shared dict
```

**Why this matters:**
- **MAF:** Data flow is explicit and traceable. Each executor sends specific messages to its downstream target. No hidden side effects.
- **LangGraph:** All nodes read/write the same shared `TypedDict`. Powerful but can create implicit dependencies.

---

## Slide 39: Differentiator #4 — Production Stack Built-In

| Production Need | Microsoft Agent Framework | LangChain/LangGraph |
|---|---|---|
| **Tracing** | `enable_instrumentation()` — native OTel | Community package, not first-party |
| **Azure Monitor** | `configure_azure_monitor()` — one line | Manual SDK integration |
| **Container deploy** | DevUI one-click to Azure Container Apps | Manual Dockerfile + deploy scripts |
| **Auth middleware** | DevUI includes Bearer token auth, CORS | Not applicable |
| **Resource config** | `agent.yaml` (CPU, memory, ports) | Manual container configuration |
| **Hosted agents** | Microsoft Foundry integration | Not supported |

**MAF philosophy:** The framework handles the boring-but-critical production plumbing so you can focus on agent logic.

---

## Slide 40: Differentiator #5 — Smaller API Surface

**Microsoft Agent Framework — 6 core concepts:**

| Concept | Purpose |
|---|---|
| `Agent` | LLM wrapper with tools and structured output |
| `@tool` | Turn a function into an agent tool |
| `@executor` | Turn a function into a workflow node |
| `WorkflowBuilder` | Connect executors into a graph |
| `WorkflowContext` | State, messaging, and output in workflow nodes |
| `serve()` | Launch visual debugger |

**LangChain requires understanding:** Chains, Runnables, LCEL, Agents, AgentExecutor, Tools, OutputParsers, PromptTemplates, ChatPromptTemplates, Callbacks, Memory, Retrievers, DocumentLoaders, TextSplitters, VectorStores, and more.

> **Fewer concepts = faster onboarding = fewer bugs.**

---

## Slide 41: Honest Trade-offs

**Where LangChain/LangGraph has advantages:**

| Area | LangChain/LangGraph Strength |
|---|---|
| **Provider ecosystem** | 700+ integrations (Anthropic, Google, Cohere, HuggingFace, etc.) vs MAF's Azure/OpenAI focus |
| **Community & adoption** | Larger community, more tutorials, StackOverflow answers |
| **RAG patterns** | Battle-tested RAG abstractions (retrievers, document loaders, text splitters) |
| **Vector store breadth** | 50+ vector store integrations vs Azure AI Search |
| **Quick prototyping** | LCEL pipe operator is faster for simple chains |

**When to choose MAF:**
- Building multi-agent workflows (not linear chains)
- Need production observability out of the box
- Deploying to Azure ecosystem
- Want visual debugging without a paid SaaS
- Need Python + .NET support
- Prefer explicit orchestration over implicit state mutation

**When to choose LangChain/LangGraph:**
- Need broad provider support (non-OpenAI models)
- Building RAG-heavy applications
- Rapid prototyping of simple chains
- Leveraging the large LangChain ecosystem

---

## Slide 42: Side-by-Side — Building the Same Workflow

**The task:** Route customer messages to order processing or conversation handling.

```python
# Microsoft Agent Framework (17 lines)
workflow = (
    WorkflowBuilder(start_executor=route_intent, max_iterations=8)
    .add_switch_case_edge_group(
        route_intent,
        [
            Case(condition=_is_order, target=update_order),
            Case(condition=_is_conversation, target=skip_order_update),
            Default(target=on_error),
        ],
    )
    .add_edge(update_order, respond)
    .add_edge(skip_order_update, respond)
    .build()
)
result = await workflow.run("I want a cheeseburger")
```

```python
# LangGraph (20 lines)
graph = StateGraph(AgentState)
graph.add_node("classify", classify_intent)
graph.add_node("update_order", update_order)
graph.add_node("skip_order", skip_order)
graph.add_node("respond", respond)
graph.add_conditional_edges(
    "classify",
    route_by_intent,
    {"order": "update_order", "conversation": "skip_order", "error": "error"}
)
graph.add_edge("update_order", "respond")
graph.add_edge("skip_order", "respond")
graph.set_entry_point("classify")
graph.set_finish_point("respond")
app = graph.compile()
result = await app.ainvoke({"messages": [HumanMessage(content="...")]})
```

Both approaches work. MAF's `Case`/`Default` pattern reads more declaratively. LangGraph's approach is familiar to state machine practitioners.

---

## Closing

---

## Slide 43: Key Takeaways

1. **Agent orchestration** decomposes complex AI tasks into specialized, composable agents
2. **WorkflowBuilder** provides declarative, validated graph construction with conditional routing
3. **Structured output** with `response_format=PydanticModel` ensures reliable inter-agent data exchange
4. **Brand personality** is data-driven and injected at runtime — keeping agent logic clean
5. **DevUI + OpenTelemetry** give you visual debugging and production observability from day one
6. **The path from prototype to production is a straight line** — CLI → DevUI → Azure Container Apps

---

## Slide 44: Resources

| Resource | Link |
|---|---|
| Microsoft Agent Framework | `github.com/microsoft/agent-framework` |
| This demo codebase | (your repo link) |
| Agent Framework DevUI docs | Framework documentation |
| Azure OpenAI Service | `learn.microsoft.com/azure/ai-services/openai` |
| OpenTelemetry GenAI conventions | `opentelemetry.io/docs/specs/semconv/gen-ai` |

---

## Slide 45: Q&A

**Thank you!**

Try it yourself:

```bash
git clone <repo-url>
cd "Microsoft Agent Framework"
uv sync
uv run ./workflow_conditional.py
```

---

## Appendix: Demo Scripts

### Demo 1: The Running Application (after Section 1)

```bash
uv run ./workflow_conditional.py
# Choose brand: 1 (Contoso Restaurant)
# Choose style: formal
# Type: "I'd like a cheeseburger with fries and a cola"
# Watch streaming response with brand personality
# Type: "Actually, make that a double patty"
# Watch order update flow
# Type: "That's all, let me check out"
# Watch confirm_order tool execution
```

### Demo 2: Agent Design (during Section 3)

Open `classification_flow.py` and walk through:
- The `Agent()` constructor with `response_format=IntentDecision`
- The multi-tier fallback parsing chain
- No tools — pure classification agent

Open `order_flow.py` and show:
- `response_format=OrderUpdate` for structured order extraction
- `tools=[get_menu, get_menu_with_codes]` for menu lookup
- The `_extract_order_object` normalization for handling LLM drift

### Demo 3: Workflow Graph (during Section 4)

```bash
uv run ./workflow_conditional.py --devui
# Browser opens automatically at http://localhost:8094
# Show the workflow graph visualization
# Send "Hi" → watch greeting short-circuit (no LLM classification)
# Send "I want a burger" → watch full order flow
# Send "What's on the menu?" → watch conversation flow
```

### Demo 4: Brand Personality Switch (during Section 6)

```bash
# Run 1: Contoso Restaurant
uv run ./workflow_conditional.py
# Choose brand 1, type: "I'd like a classic burger with extra cheese"
# Note warm, home-style response

# Run 2: Chipotle
uv run ./workflow_conditional.py
# Choose brand 4, type: "I'd like a classic burger with extra cheese"
# Note bold, sustainability-focused response
```

### Demo 5: Observability (during Section 7)

```bash
# Option A: Console tracing
uv run ./workflow_conditional.py --otel
# Place an order and examine agent spans in terminal output
# Show: agent names, token counts, tool calls, model responses

# Option B: Aspire Dashboard
docker compose -f docker-compose.aspire-dashboard.yml up -d
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
uv run ./workflow_conditional.py --otel
# Open http://localhost:18888 for visual trace explorer
```

---

## Appendix: Duration Guide

| Section | Topic | Duration | Demo |
|---|---|---|---|
| 1 | Introduction & Motivation | 5 min | Demo 1: Running App |
| 2 | Architecture Overview | 5 min | — |
| 3 | Agent Design Patterns | 10 min | Demo 2: Agent Design |
| 4 | Workflow Orchestration | 10 min | Demo 3: Workflow Graph |
| 5 | State Management & Data Flow | 7 min | — |
| 6 | Brand Personality & Prompt Engineering | 7 min | Demo 4: Brand Switch |
| 7 | Observability & Debugging | 7 min | Demo 5: OTel/DevUI |
| 8 | Deployment & Production | 4 min | — |
| 9 | Why MAF? (vs LangChain/LangGraph) | 7 min | — |
| — | Q&A | 3 min | — |
| **Total** | | **65 min** | |
