"""Model Registry — Load YAML config and create LLMClient instances.

Usage:
    registry = ModelRegistry()
    client = registry.get("agent_iteration")  # → medium tier LLMClient
    client = registry.get_tier("small")        # → small tier LLMClient
    info = registry.resolve("agent_iteration")  # → {"tier","provider","model"}
"""

import os
import yaml
from typing import Optional

from llm_client import LLMClient

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "models.yaml")


class ModelRegistry:
    """Load model registry from YAML. Provides tiered LLMClient resolution."""

    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self._data: dict = {}
        self._load()

    def _load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path) as f:
                self._data = yaml.safe_load(f) or {}
        else:
            self._data = {"tiers": {}, "routing": {}}

    def resolve(self, task: str) -> dict:
        """Resolve a task to (tier, provider_config)."""
        routing = self._data.get("routing", {})
        tier_name = routing.get(task, "medium")
        return self._resolve_tier(tier_name)

    def _resolve_tier(self, tier_name: str) -> dict:
        tier = self._data.get("tiers", {}).get(tier_name)
        if not tier:
            return {"tier": "medium", "provider": {}, "error": f"tier {tier_name} not found"}
        providers = tier.get("providers", [])
        for p in providers:
            api_key = os.environ.get(p.get("api_key_env", ""), "")
            if api_key or p.get("api_key_env") == "":
                return {
                    "tier": tier_name,
                    "provider": p,
                    "api_key": api_key,
                }
        return {"tier": tier_name, "provider": providers[0] if providers else {},
                "api_key": os.environ.get(providers[0].get("api_key_env", ""), "") if providers else ""}

    def get(self, task: str) -> Optional[LLMClient]:
        """Get an LLMClient for the given task type."""
        info = self.resolve(task)
        p = info.get("provider", {})
        if not p:
            return None
        return LLMClient(
            base_url=p.get("base_url", ""),
            api_key=info.get("api_key", ""),
            model=p.get("model", "deepseek-v4-flash"),
        )

    def get_tier(self, tier_name: str) -> Optional[LLMClient]:
        """Get an LLMClient for a named tier."""
        info = self._resolve_tier(tier_name)
        p = info.get("provider", {})
        if not p:
            return None
        return LLMClient(
            base_url=p.get("base_url", ""),
            api_key=info.get("api_key", ""),
            model=p.get("model", "deepseek-v4-flash"),
        )

    def get_config(self) -> dict:
        return dict(self._data)

    def get_fusion_config(self) -> dict:
        """Get fusion panel pricing configuration (P3-a).

        Returns:
            dict with keys: enabled, panel (list of tier configs),
            synthesized_cost (input_per_1k, output_per_1k), max_fusion_calls.
            Returns default config if fusion section not present.
        """
        fusion = self._data.get("fusion", {})
        if not fusion:
            return {
                "enabled": False,
                "panel": [],
                "synthesized_cost": {"input_per_1k": 0.0, "output_per_1k": 0.0},
                "max_fusion_calls": 0,
            }
        return {
            "enabled": fusion.get("enabled", False),
            "panel": fusion.get("panel", []),
            "synthesized_cost": fusion.get("synthesized_cost", {"input_per_1k": 0.0, "output_per_1k": 0.0}),
            "max_fusion_calls": fusion.get("max_fusion_calls", 50),
        }

    def get_fusion_cost(self, input_tokens: int = 0, output_tokens: int = 0) -> float:
        """Calculate cost for a single fusion gate evaluation.

        Uses the synthesized_cost from models.yaml fusion section.
        """
        cfg = self.get_fusion_config()
        cost = cfg.get("synthesized_cost", {})
        input_cost = (input_tokens / 1000.0) * cost.get("input_per_1k", 0.0)
        output_cost = (output_tokens / 1000.0) * cost.get("output_per_1k", 0.0)
        return round(input_cost + output_cost, 8)
