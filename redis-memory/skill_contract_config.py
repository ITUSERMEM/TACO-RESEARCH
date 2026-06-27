"""ContractConfig — 灰度配置，Redis Hash 存储。

Usage:
    config = ContractConfig(redis_client)
    if config.is_enabled(skill_name):
        # run contract validation
    config.set_log_only(False)  # 启用阻断模式
"""

import json
from typing import Optional

from redis import Redis


class ContractConfig:
    """SkillContract 灰度配置，每个 skill 可独立启用/禁用。"""

    CONFIG_KEY = "academic:contract:config"

    def __init__(self, redis_client: Redis):
        self.r = redis_client
        self._ensure_defaults()

    def _ensure_defaults(self):
        if not self.r.exists(self.CONFIG_KEY):
            self.r.hset(self.CONFIG_KEY, mapping={
                "enabled_skills": '["research-lit", "paper-figure"]',
                "pre_validation": "true",
                "entropy_monitor": "true",
                "post_voting": "false",
                "log_only": "true",
            })

    def is_enabled(self, skill_name: str) -> bool:
        raw = self.r.hget(self.CONFIG_KEY, "enabled_skills")
        if not raw:
            self._ensure_defaults()
            raw = self.r.hget(self.CONFIG_KEY, "enabled_skills")
        enabled = json.loads(raw or "[]")
        return skill_name in enabled

    def is_log_only(self) -> bool:
        raw = self.r.hget(self.CONFIG_KEY, "log_only")
        return raw == "true" if raw else True

    def is_pre_validation_enabled(self) -> bool:
        raw = self.r.hget(self.CONFIG_KEY, "pre_validation")
        return raw == "true" if raw else True

    def is_entropy_monitor_enabled(self) -> bool:
        raw = self.r.hget(self.CONFIG_KEY, "entropy_monitor")
        return raw == "true" if raw else True

    def is_post_voting_enabled(self) -> bool:
        raw = self.r.hget(self.CONFIG_KEY, "post_voting")
        return raw == "true" if raw else False

    def enable_skill(self, skill_name: str):
        enabled = json.loads(self.r.hget(self.CONFIG_KEY, "enabled_skills") or "[]")
        if skill_name not in enabled:
            enabled.append(skill_name)
            self.r.hset(self.CONFIG_KEY, "enabled_skills", json.dumps(enabled))

    def disable_skill(self, skill_name: str):
        enabled = json.loads(self.r.hget(self.CONFIG_KEY, "enabled_skills") or "[]")
        if skill_name in enabled:
            enabled.remove(skill_name)
            self.r.hset(self.CONFIG_KEY, "enabled_skills", json.dumps(enabled))

    def set_log_only(self, value: bool):
        self.r.hset(self.CONFIG_KEY, "log_only", "true" if value else "false")

    def toggle_entropy_monitor(self, enabled: bool):
        self.r.hset(self.CONFIG_KEY, "entropy_monitor", "true" if enabled else "false")

    def toggle_post_voting(self, enabled: bool):
        self.r.hset(self.CONFIG_KEY, "post_voting", "true" if enabled else "false")

    def get_all(self) -> dict:
        return self.r.hgetall(self.CONFIG_KEY)
