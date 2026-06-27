"""Local semantic cache for LLM responses using RediSearch vector similarity.

Replaces Redis Cloud's LangCache service with a local implementation
using RediSearch vector embeddings + cosine distance.
"""

import hashlib
import json
import os
import shlex
import time
from typing import Any, Optional

import numpy as np
from redis import Redis

from agent_memory import VECTOR_DIM, _embed

_INDEX_CACHE = f"""
FT.CREATE idx:cache ON JSON PREFIX 1 cache: SCHEMA
    $.taskType        AS taskType        TAG     SORTABLE
    $.prompt          AS prompt          TEXT    SORTABLE
    $.response        AS response        TEXT
    $.model           AS model           TAG
    $.embedding       AS embedding       VECTOR FLAT 6 TYPE FLOAT32 DIM {VECTOR_DIM} DISTANCE_METRIC COSINE
    $.createdAt       AS createdAt       NUMERIC SORTABLE
    $.hitCount        AS hitCount        NUMERIC
    $.attributes.*    AS attr_*          TAG
"""

_CACHE_MAX_SIZE = 5000
_CACHE_TTL = 86400 * 7  # 7 days


def _ensure_cache_index(r: Redis):
    try:
        r.execute_command(*shlex.split(_INDEX_CACHE))
    except Exception as e:
        msg = str(e).lower()
        if "already exists" not in msg and "index already exists" not in msg:
            raise


class SemanticCache:
    """Semantic cache for LLM responses using RediSearch vector similarity.

    Usage:
        cache = SemanticCache(task_type="review")
        result = cache.search("What is attention?")
        if result:
            response = result["response"]
        else:
            response = llm.generate(...)
            cache.set("What is attention?", response, model="glm-5.2")
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        task_type: str = "default",
        similarity_threshold: float = 0.50,
        max_size: int = _CACHE_MAX_SIZE,
        ttl: int = _CACHE_TTL,
    ):
        self.r = Redis.from_url(redis_url, decode_responses=True)
        self.task_type = task_type
        self.threshold = similarity_threshold
        self.max_size = max_size
        self.ttl = ttl
        _ensure_cache_index(self.r)

    def _cache_key(self, prompt_hash: str) -> str:
        return f"cache:{self.task_type}:{prompt_hash[:16]}"

    def search(
        self,
        prompt: str,
        attributes: Optional[dict[str, str]] = None,
        k: int = 5,
    ) -> Optional[dict[str, Any]]:
        """Search cache for semantically similar prompt.

        Returns cached response dict if hit, None if miss.
        """
        filters = [f"@taskType:{{{self.task_type}}}"]
        if attributes:
            for key, val in attributes.items():
                filters.append(f"@attr_{key}:{{{val}}}")

        import struct
        query_vec = _embed(prompt)
        vec_blob = struct.pack(f'{VECTOR_DIM}f', *query_vec)
        escaped_filter = " ".join(filters).replace('-', '\\-')

        try:
            result = self.r.execute_command(
                "FT.SEARCH", "idx:cache",
                f"{escaped_filter}=>[KNN {k} @embedding $vec AS embedding_score]",
                "PARAMS", "2", "vec", vec_blob,
                "SORTBY", "embedding_score", "ASC",
                "RETURN", "6", "prompt", "response", "model", "createdAt", "hitCount", "embedding_score",
                "DIALECT", "2",
                "LIMIT", "0", str(k),
            )
            if not result or result[0] == 0:
                return None

            best: Optional[dict] = None
            best_key: Optional[str] = None
            best_dist = float('inf')
            for i in range(1, len(result), 2):
                key = result[i]
                fields = result[i + 1]
                entry = {}
                for j in range(0, len(fields), 2):
                    entry[fields[j]] = fields[j + 1]

                distance = float(entry.get("embedding_score", 1.0))

                if distance <= (1.0 - self.threshold) and distance < best_dist:
                    best = entry
                    best_key = key
                    best_dist = distance

            if best and best_key:
                self._increment_hit_count(best_key)
                return best
            return None

        except Exception:
            return None

    def set(
        self,
        prompt: str,
        response: str,
        model: str = "unknown",
        attributes: Optional[dict[str, str]] = None,
        ttl: Optional[int] = None,
    ) -> str:
        """Store a prompt-response pair in cache."""
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        key = self._cache_key(prompt_hash)

        doc = {
            "taskType": self.task_type,
            "prompt": prompt,
            "response": response,
            "model": model,
            "embedding": _embed(prompt),
            "createdAt": time.time(),
            "hitCount": 0,
            "attributes": attributes or {},
        }
        self.r.json().set(key, "$", doc)
        self.r.expire(key, ttl or self.ttl)

        self._evict_if_needed()
        return key

    def stats(self) -> dict[str, Any]:
        try:
            info = self.r.execute_command("FT.INFO idx:cache")
            info_dict = {}
            for i in range(0, len(info), 2):
                info_dict[info[i].decode() if isinstance(info[i], bytes) else info[i]] = (
                    info[i + 1].decode() if isinstance(info[i + 1], bytes) else info[i + 1]
                )
            count = int(info_dict.get("num_docs", 0))
        except Exception:
            count = 0

        return {
            "task_type": self.task_type,
            "threshold": self.threshold,
            "estimated_size": count,
            "max_size": self.max_size,
        }

    def _increment_hit_count(self, key: str):
        try:
            self.r.execute_command("JSON.NUMINCRBY", key, "$.hitCount", 1)
        except Exception:
            pass

    def _evict_if_needed(self):
        try:
            info = self.r.execute_command("FT.INFO idx:cache")
            info_dict = {}
            for i in range(0, len(info), 2):
                key = info[i].decode() if isinstance(info[i], bytes) else info[i]
                val = info[i + 1].decode() if isinstance(info[i + 1], bytes) else info[i + 1]
                info_dict[key] = val
            count = int(info_dict.get("num_docs", 0))
            if count > self.max_size:
                old = self.r.execute_command(
                    f"FT.SEARCH idx:cache * SORTBY createdAt ASC RETURN 0 LIMIT 0 {count - self.max_size}"
                )
                if old and old[0] > 0:
                    for i in range(1, len(old), 2):
                        self.r.delete(old[i])
        except Exception:
            pass
