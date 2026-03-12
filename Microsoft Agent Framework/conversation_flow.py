import json
from pathlib import Path
from typing import Annotated, AsyncGenerator

from agent_framework import Agent, AgentResponseUpdate, tool
from agent_framework.openai import OpenAIChatClient


@tool
def get_menu(
    category: Annotated[
        str,
        "Optional menu category to filter: 'burgers', 'vegetarian', 'fries', or 'drinks'. "
        "Leave empty to get the full menu.",
    ] = "",
) -> str:
    """Retrieve the restaurant menu. Call this tool when you need to look up menu items, prices, sizes, toppings, or available options."""
    menu_path = Path(__file__).parent / "prompts" / "menu.txt"
    if not menu_path.exists():
        return "Menu unavailable."
    text = menu_path.read_text(encoding="utf-8")
    if category:
        # Extract the requested section if present
        sections = text.split("## ")
        for section in sections:
            if section.strip().lower().startswith(category.strip().lower()):
                return f"## {section.strip()}"
    return text


@tool
def get_menu_with_codes(
    category: Annotated[
        str,
        "Optional category to filter: 'items' for product SKUs, 'burger toppings' for topping codes. "
        "Leave empty to get the full coded menu.",
    ] = "",
) -> str:
    """Retrieve the menu with product codes and topping codes. Call this tool when you need to look up product SKUs, resolve item codes, or get topping codes for order processing."""
    menu_path = Path(__file__).parent / "prompts" / "menu_with_codes.txt"
    if not menu_path.exists():
        return "Coded menu unavailable."
    text = menu_path.read_text(encoding="utf-8")
    if category:
        sections = text.split("## ")
        for section in sections:
            if section.strip().lower().startswith(category.strip().lower()):
                return f"## {section.strip()}"
    return text


@tool
def confirm_order(**kwargs) -> str:
    """Produce a checkout summary for the current order. Call this tool when the customer wants to confirm, review, finalize, or check out their order. The order data is injected automatically."""
    order = kwargs.get("current_order", {})
    items = order.get("items", []) if isinstance(order, dict) else []
    if not items:
        return "The order is empty. Nothing to confirm."

    lines: list[str] = ["=== Order Confirmation ===", ""]
    total_items = 0
    for i, item in enumerate(items, start=1):
        name = item.get("name", "Unknown item")
        qty = item.get("quantity", 1)
        total_items += qty
        size = item.get("size", "")
        options = item.get("options", [])
        notes = item.get("notes", "")

        line = f"{i}. {name} x{qty}"
        if size:
            line += f" ({size})"
        if options:
            line += f" - {', '.join(str(o) for o in options)}"
        if notes:
            line += f" [{notes}]"
        lines.append(line)

    lines.append("")
    lines.append(f"Total items: {total_items}")
    lines.append("")
    lines.append("Ready to place this order? Say 'yes' to confirm or tell me any changes.")
    return "\n".join(lines)


class ConversationFlow:
    """Restaurant attendant response flow."""

    def __init__(self, client: OpenAIChatClient):
        self._agent = Agent(
            client=client,
            name="RestaurantAttendant",
            instructions=(
                "You are a restaurant attendant in a multi-turn order conversation. "
                "Be concise, accurate, and friendly. "
                "If required order details are missing, ask one focused follow-up question. "
                "When the order is clear, summarize items and ask for confirmation. "
                "Use the get_menu tool to look up menu items, sizes, toppings, and options "
                "whenever the customer asks about the menu or you need to verify item availability. "
                "Use the confirm_order tool when the customer wants to review, finalize, or check out "
                "their order. The tool reads the current order automatically — no arguments needed."
            ),
            tools=[get_menu, confirm_order],
        )

    async def respond(
        self,
        chat_history: list[dict],
        current_order: dict,
        brand_instructions: str,
        customer_style_instructions: str,
        order_summary: str | None = None,
    ) -> str:
        payload = {
            "brand_voice": brand_instructions,
            "customer_persona": customer_style_instructions,
            "current_order": current_order,
            "order_update_summary": order_summary or "",
            "recent_history": chat_history[-10:],
            "response_rules": [
                "Keep the response under 120 words.",
                "Do not invent menu items. Use get_menu to verify.",
                "Use plain ASCII punctuation.",
            ],
        }

        response = await self._agent.run(json.dumps(payload, ensure_ascii=True), current_order=current_order)
        return response.text.strip()

    async def stream_respond(
        self,
        chat_history: list[dict],
        current_order: dict,
        brand_instructions: str,
        customer_style_instructions: str,
        order_summary: str | None = None,
    ) -> AsyncGenerator[AgentResponseUpdate, None]:
        payload = {
            "brand_voice": brand_instructions,
            "customer_persona": customer_style_instructions,
            "current_order": current_order,
            "order_update_summary": order_summary or "",
            "recent_history": chat_history[-10:],
            "response_rules": [
                "Keep the response under 120 words.",
                "Do not invent menu items. Use get_menu to verify.",
                "Use plain ASCII punctuation.",
            ],
        }

        stream = self._agent.run(json.dumps(payload, ensure_ascii=True), stream=True, current_order=current_order)
        async for update in stream:
            yield update
