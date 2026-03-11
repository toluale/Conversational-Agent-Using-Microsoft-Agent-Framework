"""Restaurant ordering workflow with conditional edges, workflow state, and DevUI.

Demonstrates Microsoft Agent Framework WorkflowBuilder with:
- intent routing (order vs conversation)
- conditional edges
- order update branch
- explicit state updates via WorkflowContext.set_state/get_state
- DevUI integration for graph visualization

Run:
    uv run .\\worflow_conditional.py
    uv run .\\worflow_conditional.py --devui
"""

import asyncio
import json
import os
import sys
from collections.abc import Callable
from typing import Any

_GREETING_WORDS = {"hello", "hi", "hey", "greetings", "howdy", "hola", "good morning", "good afternoon", "good evening"}

from agent_framework import WorkflowBuilder, WorkflowContext, executor
from agent_framework.exceptions import ChatClientException
from agent_framework.openai import OpenAIChatClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv
from brand_personality import BrandPersonalityRegistry, get_customer_style_instructions
from classification_flow import OrderIntentFlow
from conversation_flow import ConversationFlow
from order_flow import OrderFlow


load_dotenv(override=True)


async_credential: DefaultAzureCredential | None = None

# Fallback persistent state for environments where workflow context state
# does not survive between runs (for example, repeated DevUI sends).
_PERSISTENT_SESSION_STATE: dict[str, Any] = {
    "chat_history": [],
    "current_order": {"items": []},
    "last_intent": "",
    "last_intent_reason": "",
    "order_summary": "",
}


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_client() -> OpenAIChatClient:
    """Build a chat client from API_HOST settings."""
    global async_credential
    """
    api_host = os.getenv("API_HOST", "openai").strip().lower()
    if api_host == "azure":
        endpoint = _require_env("AZURE_OPENAI_ENDPOINT").rstrip("/")
        deployment = _require_env("AZURE_OPENAI_CHAT_DEPLOYMENT")
        async_credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(async_credential, "https://cognitiveservices.azure.com/.default")
        return OpenAIChatClient(
            base_url=f"{endpoint}/openai/v1/",
            api_key=token_provider,
            model_id=deployment,
        )

    if api_host == "github":
        token = _require_env("GITHUB_TOKEN")
        return OpenAIChatClient(
            base_url="https://models.github.ai/inference",
            api_key=token,
            model_id=os.getenv("GITHUB_MODEL", "openai/gpt-5-mini"),
        )
    """
    api_key = _require_env("OPENAI_API_KEY")
    return OpenAIChatClient(
        api_key=api_key,
        model_id=os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
    )


def _is_order(envelope: Any) -> bool:
    if isinstance(envelope, dict):
        return envelope.get("intent") == "order"
    if isinstance(envelope, str):
        try:
            parsed = json.loads(envelope)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, dict) and parsed.get("intent") == "order"
    return False


def _is_conversation(envelope: Any) -> bool:
    if isinstance(envelope, dict):
        return envelope.get("intent") == "conversation"
    if isinstance(envelope, str):
        try:
            parsed = json.loads(envelope)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, dict) and parsed.get("intent") == "conversation"
    return False


def _is_greeting(envelope: Any) -> bool:
    if isinstance(envelope, dict):
        return envelope.get("intent") == "greeting"
    if isinstance(envelope, str):
        try:
            parsed = json.loads(envelope)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, dict) and parsed.get("intent") == "greeting"
    return False


def _load_session_state(ctx: WorkflowContext[Any, Any]) -> dict[str, Any]:
    """Load session state from workflow context, falling back to persistent store."""
    chat_history = ctx.get_state("chat_history", None)
    current_order = ctx.get_state("current_order", None)
    last_intent = ctx.get_state("last_intent", None)
    last_intent_reason = ctx.get_state("last_intent_reason", None)
    order_summary = ctx.get_state("order_summary", None)

    return {
        "chat_history": list(chat_history) if isinstance(chat_history, list) else list(_PERSISTENT_SESSION_STATE["chat_history"]),
        "current_order": dict(current_order) if isinstance(current_order, dict) else dict(_PERSISTENT_SESSION_STATE["current_order"]),
        "last_intent": str(last_intent) if last_intent is not None else str(_PERSISTENT_SESSION_STATE["last_intent"]),
        "last_intent_reason": (
            str(last_intent_reason)
            if last_intent_reason is not None
            else str(_PERSISTENT_SESSION_STATE["last_intent_reason"])
        ),
        "order_summary": str(order_summary) if order_summary is not None else str(_PERSISTENT_SESSION_STATE["order_summary"]),
    }

## Added this to guarantee persistent session state
def _save_session_state(ctx: WorkflowContext[Any, Any], state: dict[str, Any]) -> None:
    """Save session state to workflow context and persistent fallback store."""
    chat_history = list(state.get("chat_history", []))
    current_order = dict(state.get("current_order", {"items": []}))
    last_intent = str(state.get("last_intent", ""))
    last_intent_reason = str(state.get("last_intent_reason", ""))
    order_summary = str(state.get("order_summary", ""))

    ctx.set_state("chat_history", chat_history)
    ctx.set_state("current_order", current_order)
    ctx.set_state("last_intent", last_intent)
    ctx.set_state("last_intent_reason", last_intent_reason)
    ctx.set_state("order_summary", order_summary)

    _PERSISTENT_SESSION_STATE["chat_history"] = chat_history
    _PERSISTENT_SESSION_STATE["current_order"] = current_order
    _PERSISTENT_SESSION_STATE["last_intent"] = last_intent
    _PERSISTENT_SESSION_STATE["last_intent_reason"] = last_intent_reason
    _PERSISTENT_SESSION_STATE["order_summary"] = order_summary


def create_chat_workflow(
    client: OpenAIChatClient,
    brand_name: str = "Contoso Restaurant",
    customer_style: str = "formal",
    stream_callback: Callable[[str], None] | None = None,
):
    """Create a DevUI-friendly chat workflow that accepts plain text input."""
    intent_flow = OrderIntentFlow(client)
    order_flow = OrderFlow(client)
    conversation_flow = ConversationFlow(client)
    brand_registry = BrandPersonalityRegistry()

    @executor(id="route_intent")
    async def route_intent(user_message: str, ctx: WorkflowContext[str, dict]) -> None:
        session_state = _load_session_state(ctx)
        chat_history = list(session_state["chat_history"])
        current_order = dict(session_state["current_order"])
        message = str(user_message).strip()

        if not message:
            await ctx.yield_output({"error": "user_message is required"})
            return

        chat_history.append({"role": "user", "content": message})

        # Detect greetings early to skip intent classification LLM call
        if message.lower().strip("!.,? ") in _GREETING_WORDS:
            intent = "greeting"
            reason = "Customer greeting detected"
        else:
            decision = await intent_flow.classify(chat_history, current_order)
            intent = decision.intent
            reason = decision.reason

        session_state["chat_history"] = chat_history
        session_state["current_order"] = current_order
        session_state["last_intent"] = intent
        session_state["last_intent_reason"] = reason
        _save_session_state(ctx, session_state)

        envelope = {
            "chat_history": chat_history,
            "current_order": current_order,
            "brand_name": brand_name,
            "customer_style": customer_style,
            "intent": intent,
            "intent_reason": reason,
        }
        await ctx.send_message(json.dumps(envelope, ensure_ascii=True))

    @executor(id="update_order")
    async def update_order(envelope_json: str, ctx: WorkflowContext[str, dict]) -> None:
        envelope = json.loads(envelope_json)
        session_state = _load_session_state(ctx)
        update = await order_flow.update_order(envelope["chat_history"], envelope["current_order"])
        envelope["current_order"] = update.order.model_dump()
        envelope["order_summary"] = update.summary

        session_state["chat_history"] = envelope["chat_history"]
        session_state["current_order"] = envelope["current_order"]
        session_state["order_summary"] = envelope["order_summary"]
        _save_session_state(ctx, session_state)
        await ctx.send_message(json.dumps(envelope, ensure_ascii=True))

    @executor(id="skip_order_update")
    async def skip_order_update(envelope_json: str, ctx: WorkflowContext[str, dict]) -> None:
        envelope = json.loads(envelope_json)
        session_state = _load_session_state(ctx)
        envelope["order_summary"] = ""
        session_state["chat_history"] = envelope["chat_history"]
        session_state["current_order"] = envelope["current_order"]
        session_state["order_summary"] = ""
        _save_session_state(ctx, session_state)
        await ctx.send_message(json.dumps(envelope, ensure_ascii=True))

    @executor(id="respond")
    async def respond(envelope_json: str, ctx: WorkflowContext[str, dict]) -> None:
        envelope = json.loads(envelope_json)
        session_state = _load_session_state(ctx)
        brand_instructions = brand_registry.get_brand_instructions(envelope["brand_name"])
        customer_style_instructions = get_customer_style_instructions(envelope["customer_style"])

        # Use streaming to collect the response chunk by chunk
        chunks: list[str] = []
        async for chunk in conversation_flow.stream_respond(
            chat_history=envelope["chat_history"],
            current_order=envelope["current_order"],
            brand_instructions=brand_instructions,
            customer_style_instructions=customer_style_instructions,
            order_summary=envelope.get("order_summary", ""),
        ):
            chunks.append(chunk)
            if stream_callback:
                stream_callback(chunk)
        assistant_reply = "".join(chunks).strip()

        envelope["chat_history"].append({"role": "assistant", "content": assistant_reply})
        session_state["chat_history"] = envelope["chat_history"]
        session_state["current_order"] = envelope["current_order"]
        session_state["order_summary"] = envelope.get("order_summary", "")
        _save_session_state(ctx, session_state)

        await ctx.yield_output(
            {
                "assistant_response": assistant_reply,
                "intent": str(session_state.get("last_intent", envelope.get("intent", ""))),
                "reason": str(session_state.get("last_intent_reason", envelope.get("intent_reason", ""))),
                "current_order": envelope["current_order"],
                "chat_history": envelope["chat_history"],
            }
        )

    @executor(id="greet")
    async def greet(envelope_json: str, ctx: WorkflowContext[str, dict]) -> None:
        """Handle greeting messages by generating a welcome response."""
        envelope = json.loads(envelope_json)
        session_state = _load_session_state(ctx)
        brand_instructions = brand_registry.get_brand_instructions(envelope["brand_name"])
        customer_style_instructions = get_customer_style_instructions(envelope["customer_style"])

        # Stream a greeting response
        chunks: list[str] = []
        greeting_history = envelope["chat_history"][-2:]  # Just the greeting message
        async for chunk in conversation_flow.stream_respond(
            chat_history=greeting_history,
            current_order=envelope["current_order"],
            brand_instructions=brand_instructions,
            customer_style_instructions=customer_style_instructions,
            order_summary="",
        ):
            chunks.append(chunk)
            if stream_callback:
                stream_callback(chunk)
        assistant_reply = "".join(chunks).strip()

        envelope["chat_history"].append({"role": "assistant", "content": assistant_reply})
        session_state["chat_history"] = envelope["chat_history"]
        session_state["current_order"] = envelope["current_order"]
        _save_session_state(ctx, session_state)

        await ctx.yield_output(
            {
                "assistant_response": assistant_reply,
                "intent": "greeting",
                "reason": "Customer greeting detected",
                "current_order": envelope["current_order"],
                "chat_history": envelope["chat_history"],
            }
        )

    @executor(id="on_error")
    async def on_error(_envelope: str, ctx: WorkflowContext[str, dict]) -> None:
        await ctx.yield_output({"error": "No route for payload"})

    return (
        WorkflowBuilder(start_executor=route_intent, max_iterations=8)
        .add_edge(route_intent, greet, condition=_is_greeting)
        .add_edge(route_intent, update_order, condition=_is_order)
        .add_edge(route_intent, skip_order_update, condition=_is_conversation)
        .add_edge(route_intent, on_error)
        .add_edge(update_order, respond)
        .add_edge(skip_order_update, respond)
        .build()
    )


def _pick_brand(registry: BrandPersonalityRegistry) -> str:
    brands = registry.list_brands()
    if not brands:
        return "Contoso Restaurant"

    print("\nAvailable brands:")
    for idx, brand in enumerate(brands, start=1):
        print(f"{idx}. {brand}")

    selection = input("Choose a brand number (default 1): ").strip()
    if not selection:
        return brands[0]

    try:
        choice = int(selection)
        if 1 <= choice <= len(brands):
            return brands[choice - 1]
    except ValueError:
        pass

    return brands[0]


def _pick_customer_style() -> str:
    styles = ["formal", "casual", "genz"]
    print("\nCustomer styles:")
    for idx, style in enumerate(styles, start=1):
        print(f"{idx}. {style}")

    selection = input("Choose customer style number (default 1): ").strip()
    if not selection:
        return "formal"

    try:
        choice = int(selection)
        if 1 <= choice <= len(styles):
            return styles[choice - 1]
    except ValueError:
        pass

    return "formal"


async def run_cli() -> None:
    client = build_client()
    brand_name = _pick_brand(BrandPersonalityRegistry())
    customer_style = _pick_customer_style()

    def _print_chunk(chunk: str) -> None:
        sys.stdout.write(chunk)
        sys.stdout.flush()

    workflow = create_chat_workflow(
        client,
        brand_name=brand_name,
        customer_style=customer_style,
        stream_callback=_print_chunk,
    )

    print("\nStarting multi-turn restaurant prototype.")
    print("Type 'exit' to stop.\n")

    chat_history: list[dict] = []
    current_order: dict = {"items": []}

    # Auto-trigger greeting on startup
    print("Attendant> ", end="", flush=True)
    try:
        events = await workflow.run("Hello")
        outputs = list(events.get_outputs())
    except ChatClientException:
        outputs = []
    if outputs and "error" not in outputs[-1]:
        result = outputs[-1]
        chat_history.append({"role": "user", "content": "Hello"})
        chat_history.append({"role": "assistant", "content": result["assistant_response"]})
        print()  # newline after streamed greeting
    print()

    while True:
        user_message = input("Customer> ").strip()
        if user_message.lower() in {"exit", "quit"}:
            print("Session ended.")
            break
        if not user_message:
            continue

        payload = user_message

        print("Attendant> ", end="", flush=True)
        try:
            events = await workflow.run(payload)
            outputs = list(events.get_outputs())
        except ChatClientException as exc:
            message = str(exc)
            if "insufficient_quota" in message or "Error code: 429" in message:
                print(
                    "\nModel call failed due to quota limits for the configured provider.\n"
                    "Set API_HOST"
                )
                break
            raise

        print()  # newline after streamed output

        if not outputs:
            print("Sorry, I could not process that turn.\n")
            continue

        result = outputs[-1]
        if "error" in result:
            print(f"{result['error']}\n")
            continue

        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": result["assistant_response"]})
        current_order = dict(result.get("current_order", current_order))

        print(f"Order> {current_order}\n")

    if async_credential:
        await async_credential.close()


def run_devui() -> None:
    from agent_framework.devui import serve

    client = build_client()
    chat_workflow = create_chat_workflow(client)
    serve(entities=[chat_workflow], port=8094, auto_open=True)


if __name__ == "__main__":
    if "--devui" in sys.argv or "-devui" in sys.argv:
        run_devui()
    else:
        asyncio.run(run_cli())
