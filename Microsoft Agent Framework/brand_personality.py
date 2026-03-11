import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class BrandProfile(BaseModel):
    name: str
    tone: str
    style: str
    key_phrases: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)


class BrandPersonalityRegistry:
    """Loads brand personality metadata from the local config file."""

    def __init__(self, config_path: Path | None = None):
        base_dir = Path(__file__).parent
        self._config_path = config_path or base_dir / "brand_configs.json"
        self._profiles = self._load_profiles()

    def _load_profiles(self) -> dict[str, BrandProfile]:
        if not self._config_path.exists():
            return {}

        raw: dict[str, Any] = json.loads(self._config_path.read_text(encoding="utf-8"))
        profiles: dict[str, BrandProfile] = {}
        for key, value in raw.items():
            try:
                profiles[key] = BrandProfile.model_validate(value)
            except Exception:
                continue
        return profiles

    def list_brands(self) -> list[str]:
        return sorted(self._profiles.keys())

    def get_brand(self, brand_name: str | None) -> BrandProfile | None:
        if not brand_name:
            return None
        return self._profiles.get(brand_name)

    def get_brand_instructions(self, brand_name: str | None) -> str:
        profile = self.get_brand(brand_name)
        if profile is None:
            return (
                "Brand voice: warm, helpful, and concise. "
                "Focus on menu clarity, friendly service, and fast order completion."
            )

        phrases = ", ".join(profile.key_phrases) if profile.key_phrases else "none"
        values = ", ".join(profile.values) if profile.values else "none"
        return (
            f"Represent {profile.name}.\n"
            f"Tone: {profile.tone}.\n"
            f"Style: {profile.style}.\n"
            f"Key phrases to use naturally: {phrases}.\n"
            f"Core values to reflect: {values}."
        )


def get_customer_style_instructions(style_name: str) -> str:
    """Returns customer persona cues used by the attendant to adapt tone."""
    style = (style_name or "formal").strip().lower()
    base_dir = Path(__file__).parent

    if style == "casual":
        txt_path = base_dir / "casual.txt"
        if txt_path.exists():
            return txt_path.read_text(encoding="utf-8").strip()

    if style in {"genz", "gen-z", "gen_z"}:
        txt_path = base_dir / "genZ.txt"
        if txt_path.exists():
            return txt_path.read_text(encoding="utf-8").strip()

    return (
        "Use a professional and polite tone suitable for a formal customer. "
        "Be clear, respectful, and concise."
    )
