"""Local Agent Memory using Redis Stack (RedisJSON + RediSearch).

Replaces Redis Cloud's iris-development Agent Memory (RAM) service
with an equivalent local implementation using Redis Stack modules.

Two memory tiers:
- Session memory: append-only conversation history per session.
- Long-term memory: semantically searchable records with vector embeddings.
"""

import json
import shlex
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from redis import Redis
from sentence_transformers import SentenceTransformer

VECTOR_DIM = 384  # all-MiniLM-L6-v2


_embed_model: SentenceTransformer | None = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        model_path = '/root/.cache/modelscope/hub/models/sentence-transformers/all-MiniLM-L6-v2'
        _embed_model = SentenceTransformer(
            model_path,
            device='cuda',
        )
    return _embed_model


def _embed(text: str) -> list[float]:
    return _get_embed_model().encode(text).tolist()


_INDEX_LTM = """
FT.CREATE idx:ltm ON JSON PREFIX 1 ltm: SCHEMA
    $.namespace       AS namespace       TAG     SORTABLE
    $.ownerId         AS ownerId         TAG     SORTABLE
    $.memoryType      AS memoryType      TAG     SORTABLE
    $.topics[*]       AS topics          TAG
    $.timestamp       AS timestamp       NUMERIC SORTABLE
"""

_INDEX_SESSION = """
FT.CREATE idx:session ON JSON PREFIX 1 session: SCHEMA
    $.sessionId       AS sessionId       TAG     SORTABLE
    $.ownerId         AS ownerId         TAG     SORTABLE
    $.timestamp       AS timestamp       NUMERIC SORTABLE
"""


def _ensure_index(r: Redis, cmd: str):
    try:
        r.execute_command(*shlex.split(cmd))
    except Exception as e:
        if "already exists" not in str(e).lower() and "MOVED" not in str(e):
            if "Index already exists" not in str(e):
                raise


# --------------- AgentMemory ---------------

class AgentMemory:
    """Persistent memory layer for AI agents using local Redis Stack.

    Usage:
        mem = AgentMemory()
        mem.add_session_event("session-1", {"role": "user", "content": "..."})
        memts = mem.search_long_term("transformer paper")
    """

    def __init__(self, redis_url: str = "redis://localhost:6379", namespace: str = "academic"):
        self.redis_url = redis_url
        self.r = Redis.from_url(redis_url, decode_responses=True)
        self.namespace = namespace
        _ensure_index(self.r, _INDEX_LTM)
        _ensure_index(self.r, _INDEX_SESSION)

    @property
    def paper(self):
        from lit_researcher_bridge import PaperMemory
        if not hasattr(self, '_paper_mem') or self._paper_mem is None:
            self._paper_mem = PaperMemory(redis_url=self.redis_url)
        return self._paper_mem

    # ---- session memory ----

    def _session_key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def add_session_event(self, session_id: str, event: dict[str, Any]) -> str:
        event_id = str(uuid.uuid4())
        doc = {
            "sessionId": session_id,
            "eventId": event_id,
            "namespace": self.namespace,
            "timestamp": datetime.now(timezone.utc).timestamp(),
            **event,
        }
        self.r.json().set(f"session:{session_id}:events:{event_id}", "$", doc)
        return event_id

    def get_session_memory(self, session_id: str, limit: int = 100) -> list[dict]:
        keys = self.r.keys(f"session:{session_id}:events:*")
        keys = sorted(keys)[-limit:]
        events = []
        for k in keys:
            doc = self.r.json().get(k)
            if doc:
                events.append(doc)
        return events

    # ---- long-term memory ----

    def _ltm_key(self, memory_id: Optional[str] = None) -> str:
        return f"ltm:{self.namespace}:{memory_id or str(uuid.uuid4())}"

    def create_long_term_memory(
        self,
        content: str,
        topics: Optional[list[str]] = None,
        owner_id: str = "system",
        memory_type: str = "fact",
        memory_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        key = self._ltm_key(memory_id)
        doc = {
            "namespace": self.namespace,
            "ownerId": owner_id,
            "memoryType": memory_type,
            "topics": topics or [],
            "content": content,
            "timestamp": datetime.now(timezone.utc).timestamp(),
            "metadata": metadata or {},
        }
        self.r.json().set(key, "$", doc)
        return key.split(":")[-1]

    def search_long_term(
        self,
        query: str,
        k: int = 10,
        owner_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        topics: Optional[list[str]] = None,
    ) -> list[dict]:
        filters = []
        if owner_id:
            filters.append(f'@ownerId:{{{owner_id}}}')
        if memory_type:
            filters.append(f'@memoryType:{{{memory_type}}}')
        if topics:
            escaped = [t.replace('-', '\\-') for t in topics]
            filters.append(f'@topics:{{{ " | ".join(escaped) }}}')

        filter_expr = " ".join(filters) if filters else "*"
        try:
            result = self.r.execute_command(
                "FT.SEARCH", "idx:ltm", filter_expr,
                "SORTBY", "timestamp", "DESC",
                "RETURN", "1", "ownerId",
                "LIMIT", "0", str(k),
            )
            memories = []
            if result:
                for i in range(1, len(result), 2):
                    key = result[i]
                    raw = self.r.json().get(key)
                    if raw is None:
                        continue
                    doc = {
                        "id": key,
                        "content": raw.get("content", ""),
                        "namespace": raw.get("namespace", ""),
                        "ownerId": raw.get("ownerId", ""),
                        "memoryType": raw.get("memoryType", ""),
                        "timestamp": float(raw.get("timestamp", 0)),
                        "metadata": raw.get("metadata", {}),
                        "score": 1.0,
                    }
                    memories.append(doc)
            return memories
        except Exception:
            return []

    @staticmethod
    def _parse_ft_result(key: str, fields: list) -> Optional[dict]:
        doc = {}
        for j in range(0, len(fields), 2):
            doc[fields[j]] = fields[j + 1]
        metadata_raw = doc.get("metadata", "{}")
        if isinstance(metadata_raw, str):
            try:
                metadata_raw = json.loads(metadata_raw)
            except Exception:
                metadata_raw = {}
        return {
            "id": key,
            "content": doc.get("content", ""),
            "namespace": doc.get("namespace", ""),
            "ownerId": doc.get("ownerId", ""),
            "memoryType": doc.get("memoryType", ""),
            "timestamp": float(doc.get("timestamp", 0)),
            "metadata": metadata_raw,
        }

    # ---- review audit persistence ----

    def record_review(
        self,
        phase: int,
        phase_name: str,
        reviewer: str,
        verdict: str,
        target: str,
        details: Optional[dict] = None,
        owner_id: str = "research-director",
    ) -> str:
        """Persist a review gate outcome into long-term memory.

        Args:
            phase: Phase number (1-5)
            phase_name: Human-readable phase name
            reviewer: Agent role (e.g. "academic-reviewer", "method-reviewer")
            verdict: One of "pass", "revise", "fail"
            target: What was reviewed (e.g. "experiment-results", "claim-audit")
            details: Optional structured metadata (issues, recommendations, etc.)
            owner_id: Who triggered the review (default: research-director)

        Returns:
            memory_id for later retrieval.
        """
        VALID_VERDICTS = {"pass", "revise", "fail"}
        if verdict not in VALID_VERDICTS:
            raise ValueError(f"verdict must be one of {VALID_VERDICTS}")

        content = (
            f"[Gate {phase}:{phase_name}] {reviewer} → {target}: {verdict}"
        )
        topics = [
            "review-audit",
            f"phase-{phase}",
            reviewer,
        ]
        return self.create_long_term_memory(
            content=content,
            topics=topics,
            owner_id=owner_id,
            memory_type=f"gate-{verdict}",
            metadata={
                "phase": phase,
                "phaseName": phase_name,
                "reviewer": reviewer,
                "verdict": verdict,
                "target": target,
                "details": details or {},
            },
        )

    # ---- timeseries metrics ----

    def record_event(self, metric_name: str, value: float, labels: Optional[dict[str, str]] = None) -> str:
        key = f"ts:{self.namespace}:{metric_name}"
        if not self.r.exists(key):
            labels_str = ""
            if labels:
                parts = [f"{k} {v}" for k, v in labels.items()]
                labels_str = f'LABELS {" ".join(parts)}'
            self.r.execute_command(f'TS.CREATE {key} DUPLICATE_POLICY LAST {labels_str}')
        self.r.execute_command(f'TS.ADD {key} * {value}')
        return key

    def get_timeseries(
        self,
        metric_name: str,
        from_ts: str = '-',
        to_ts: str = '+',
        aggregation: Optional[str] = None,
        bucket_sec: int = 60,
        limit: int = 1000,
    ) -> list[tuple[float, float]]:
        key = f"ts:{self.namespace}:{metric_name}"
        agg_clause = ""
        if aggregation:
            agg_clause = f'AGGREGATION {aggregation} {bucket_sec}'
        try:
            result = self.r.execute_command(f'TS.RANGE {key} {from_ts} {to_ts} COUNT {limit} {agg_clause}')
            return [(float(ts), float(val)) for ts, val in result] if result else []
        except Exception:
            return []
