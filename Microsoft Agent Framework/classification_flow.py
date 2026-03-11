import json
import re
from typing import Literal

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient
from pydantic import BaseModel, ValidationError


class IntentDecision(BaseModel):
    intent: Literal["order", "conversation"]
    reason: str = ""


class OrderIntentFlow:
    """Intent classification using Microsoft Agent Framework only."""

    def __init__(self, client: OpenAIChatClient):
        self._agent = Agent(
            client=client,
            name="OrderIntentClassifier",
            instructions=(
                "Classify the latest customer message for a restaurant assistant. "
                "Return intent='order' when the customer is adding/removing/changing items, "
                "starting/canceling an order, or confirming checkout details. "
                "Return intent='conversation' for greetings, menu questions, policies, "
                "small talk, or general questions that do not change the order. "
                "Always include a short reason string explaining the classification."
            ),
            response_format=IntentDecision,
        )

    async def classify(self, chat_history: list[dict], current_order: dict) -> IntentDecision:
        latest_user = ""
        for message in reversed(chat_history):
            if message.get("role") == "user":
                latest_user = str(message.get("content", "")).strip()
                break

        payload = {
            "latest_user_message": latest_user,
            "current_order": current_order,
            "recent_history": chat_history[-8:],
        }
        response = await self._agent.run(json.dumps(payload, ensure_ascii=True))

        # First attempt strict JSON parsing.
        try:
            return IntentDecision.model_validate_json(response.text)
        except ValidationError:
            pass

        # Fallback: handle simple key/value text formats like:
        # intent='order'\nreason='customer asked to add fries'
        # intent: order\nreason: customer asked to add fries
        text = response.text.strip()
        intent_match = re.search(r"intent\s*[:=]\s*['\"]?(order|conversation)['\"]?", text, re.IGNORECASE)
        reason_match = re.search(r"reason\s*[:=]\s*['\"]?(.+?)['\"]?$", text, re.IGNORECASE | re.MULTILINE)
        if intent_match:
            intent = intent_match.group(1).lower()
            reason = reason_match.group(1).strip() if reason_match else ""
            return IntentDecision(intent=intent, reason=reason)

        # Last resort: attempt raw dict parsing and normalize keys.
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                intent = str(parsed.get("intent", "conversation")).strip().lower()
                reason = str(parsed.get("reason", "")).strip()
                if intent in {"order", "conversation"}:
                    return IntentDecision(intent=intent, reason=reason)
        except json.JSONDecodeError:
            pass

        raise RuntimeError(f"IntentDecision parse failed: unsupported response format: {text}")

    async def __call__(self, chat_history: list[dict], current_order: dict) -> str:
        decision = await self.classify(chat_history, current_order)
        return decision.intent
