import json
from pathlib import Path
from typing import AsyncGenerator

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient


class ConversationFlow:
    """Restaurant attendant response flow."""

    def __init__(self, client: OpenAIChatClient):
        self._menu_text = self._load_menu_text()
        self._agent = Agent(
            client=client,
            name="RestaurantAttendant",
            instructions=(
                "You are a restaurant attendant in a multi-turn order conversation. "
                "Be concise, accurate, and friendly. "
                "If required order details are missing, ask one focused follow-up question. "
                "When the order is clear, summarize items and ask for confirmation."
            ),
        )

    def _load_menu_text(self) -> str:
        menu_path = Path(__file__).parent / "prompts" / "menu.txt"
        if not menu_path.exists():
            return "Menu unavailable."
        return menu_path.read_text(encoding="utf-8")

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
            "menu": self._menu_text,
            "current_order": current_order,
            "order_update_summary": order_summary or "",
            "recent_history": chat_history[-10:],
            "response_rules": [
                "Keep the response under 120 words.",
                "Do not invent menu items.",
                "Use plain ASCII punctuation.",
            ],
        }

        response = await self._agent.run(json.dumps(payload, ensure_ascii=True))
        return response.text.strip()

    async def stream_respond(
        self,
        chat_history: list[dict],
        current_order: dict,
        brand_instructions: str,
        customer_style_instructions: str,
        order_summary: str | None = None,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "brand_voice": brand_instructions,
            "customer_persona": customer_style_instructions,
            "menu": self._menu_text,
            "current_order": current_order,
            "order_update_summary": order_summary or "",
            "recent_history": chat_history[-10:],
            "response_rules": [
                "Keep the response under 120 words.",
                "Do not invent menu items.",
                "Use plain ASCII punctuation.",
            ],
        }

        stream = self._agent.run(json.dumps(payload, ensure_ascii=True), stream=True)
        async for update in stream:
            chunk = update.text
            if chunk:
                yield chunk
