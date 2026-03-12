## Use a simple freeform schema for order updates.
## using menu.txt file instead of schemas.py
## Menu items are only designed for Contoso. Always pick 1 in the CLI interface.

import json
from typing import Any

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from pydantic import BaseModel, Field, ValidationError

from conversation_flow import get_menu, get_menu_with_codes


class OrderItem(BaseModel):
    name: str
    quantity: int = 1
    size: str | None = None
    options: list[str] = Field(default_factory=list)
    notes: str | None = None


class LLMOrder(BaseModel):
    items: list[OrderItem] = Field(default_factory=list)


class OrderUpdate(BaseModel):
    order: LLMOrder
    summary: str = ""


class OrderFlow:
    """Order extraction/update flow implemented with Microsoft Agent Framework."""

    def __init__(self, client: OpenAIChatClient):
        self._agent = Agent(
            client=client,
            name="OrderUpdateAgent",
            instructions=(
                "You update a restaurant order from conversation context. "
                "Return the full updated order each turn. "
                "Always return JSON with keys: order and summary. "
                "Only include items that appear on the restaurant menu. "
                "Use the get_menu tool to look up available items and verify what is on the menu. "
                "Use the get_menu_with_codes tool to resolve product codes when needed. "
                "If user asks for non-menu items, keep order unchanged and mention it in summary."
            ),
            response_format=OrderUpdate,
            tools=[get_menu, get_menu_with_codes],
        )

    def _extract_order_object(self, parsed: dict, current_order: dict) -> dict:
        """Extract order payload from common and nested LLM response shapes."""
        direct_candidates = (
            parsed.get("order"),
            parsed.get("current_order"),
            parsed.get("updated_order"),
        )
        for candidate in direct_candidates:
            if isinstance(candidate, dict):
                if isinstance(candidate.get("items"), list):
                    return {"items": candidate["items"]}
                if isinstance(candidate.get("order"), dict) and isinstance(candidate["order"].get("items"), list):
                    return {"items": candidate["order"]["items"]}

        if isinstance(parsed.get("items"), list):
            return {"items": parsed["items"]}

        data_obj = parsed.get("data")
        if isinstance(data_obj, dict):
            return self._extract_order_object(data_obj, current_order)

        result_obj = parsed.get("result")
        if isinstance(result_obj, dict):
            return self._extract_order_object(result_obj, current_order)

        return {"items": current_order.get("items", [])}

    def _normalize_order_object(self, order_obj: dict) -> dict:
        """Normalize item shapes so they fit OrderItem schema reliably."""
        raw_items = order_obj.get("items", []) if isinstance(order_obj, dict) else []
        normalized_items: list[dict] = []

        for raw in raw_items:
            if not isinstance(raw, dict):
                continue

            options = raw.get("options", [])
            if isinstance(options, dict):
                flattened: list[str] = []
                for key, value in options.items():
                    if isinstance(value, list):
                        joined = ", ".join(str(v) for v in value)
                        flattened.append(f"{key}: {joined}")
                    elif value in (None, "", {}):
                        continue
                    else:
                        flattened.append(f"{key}: {value}")
                options = flattened
            elif isinstance(options, str):
                options = [options]
            elif not isinstance(options, list):
                options = []

            normalized_items.append(
                {
                    "name": str(raw.get("name", "")).strip(),
                    "quantity": int(raw.get("quantity", 1) or 1),
                    "size": raw.get("size"),
                    "options": [str(o) for o in options],
                    "notes": raw.get("notes"),
                }
            )

        return {"items": normalized_items}

    async def update_order(self, chat_history: list[dict], current_order: dict) -> OrderUpdate:
        payload = {
            "current_order": current_order,
            "recent_history": chat_history[-10:],
            "task": "Return the full updated order based on the latest user input. Use get_menu to check available items.",
        }
        response = await self._agent.run(json.dumps(payload, ensure_ascii=True))

        # First try strict parsing from the expected schema.
        try:
            return OrderUpdate.model_validate_json(response.text)
        except ValidationError:
            pass

        # Fallback parser to handle common model drift like {"current_order": ...}
        # or top-level {"items": [...] } without the "order" wrapper.
        try:
            parsed: Any = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OrderUpdate parse failed: invalid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("OrderUpdate parse failed: response must be a JSON object")

        order_obj = self._normalize_order_object(self._extract_order_object(parsed, current_order))

        summary = str(parsed.get("summary", "")).strip()
        if not summary:
            summary = "Order updated from latest customer request."

        try:
            return OrderUpdate(order=LLMOrder.model_validate(order_obj), summary=summary)
        except ValidationError as exc:
            raise RuntimeError(f"OrderUpdate parse failed: {exc}") from exc

    async def __call__(self, chat_history: list[dict], current_order: dict) -> dict:
        update = await self.update_order(chat_history, current_order)
        return update.order.model_dump()
