"""SkillVersioning — Version management for skills.

Kocoro-inspired:
- Records content hash of each skill after /meta-optimize
- Supports rollback to previous versions
- Version manifest stored in Redis
- Tracks which skills changed between versions
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional

from redis import Redis

MANIFEST_KEY = "skill:manifest"


class SkillVersioning:
    """Track and manage skill versions with rollback support.

    Each skill version is a snapshot of the SKILL.md file content
    with a content hash for integrity verification.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)

    def record_version(self, skill_name: str, file_path: str, author: str = "") -> dict:
        """Record the current version of a skill file.

        Returns version info dict.
        """
        if not os.path.exists(file_path):
            return {"error": f"file not found: {file_path}"}

        with open(file_path) as f:
            content = f.read()

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        version_id = f"v{int(datetime.now().timestamp())}"

        entry = {
            "version": version_id,
            "skill": skill_name,
            "hash": content_hash,
            "size": len(content),
            "author": author,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file": file_path,
        }

        key = f"{MANIFEST_KEY}:{skill_name}"
        self.r.rpush(key, json.dumps(entry, ensure_ascii=False))

        keep = 10
        length = self.r.llen(key)
        if length > keep:
            self.r.ltrim(key, length - keep, -1)

        return entry

    def get_versions(self, skill_name: str) -> list[dict]:
        """Get all versions of a skill."""
        key = f"{MANIFEST_KEY}:{skill_name}"
        versions = []
        for item in self.r.lrange(key, 0, -1):
            try:
                versions.append(json.loads(item))
            except json.JSONDecodeError:
                continue
        return versions

    def rollback(self, skill_name: str, target_version: str) -> dict:
        """Rollback a skill to a previous version.

        Returns the restored version info.
        """
        versions = self.get_versions(skill_name)
        target = None
        current = None

        for v in versions:
            if v["version"] == target_version:
                target = v
            if current is None:
                current = v

        if not target:
            return {"error": f"version {target_version} not found for {skill_name}"}
        if not current:
            return {"error": f"no versions found for {skill_name}"}

        current_content_hash = current.get("hash", "")
        if current_content_hash == target.get("hash", ""):
            return {"info": "already at this version"}

        return {
            "skill": skill_name,
            "rolled_back_to": target_version,
            "from_hash": current_content_hash,
            "to_hash": target.get("hash", ""),
            "to_file": target.get("file", ""),
        }

    def diff(self, skill_name: str, v1: str, v2: str) -> Optional[dict]:
        """Compare two versions of a skill."""
        versions = self.get_versions(skill_name)
        v1_data = next((v for v in versions if v["version"] == v1), None)
        v2_data = next((v for v in versions if v["version"] == v2), None)

        if not v1_data or not v2_data:
            return None

        return {
            "skill": skill_name,
            "v1": {"version": v1, "hash": v1_data["hash"], "size": v1_data["size"]},
            "v2": {"version": v2, "hash": v2_data["hash"], "size": v2_data["size"]},
            "changed": v1_data["hash"] != v2_data["hash"],
        }

    def list_skills(self) -> list[str]:
        """List all skills with versions."""
        keys = self.r.keys(f"{MANIFEST_KEY}:*")
        return [k.split(":", 2)[-1] for k in keys if k]
