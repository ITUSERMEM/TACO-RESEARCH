"""
cost_ledger.py - Redis-backed append-only cost ledger with snapshotMax reconciliation.

Implements the K-Dense BYOK cost/ledger.ts pattern: every LLM call's cost is
appended to a per-session Redis List, a running project total is maintained via
INCRBYFLOAT for O(1) budget checks, and two independent measurement paths can be
reconciled by taking the field-wise maximum of their CostSnapshot dicts.

Redis key schema
----------------
costs:{project_id}:{session_id}  - List[str]   append-only JSON entries
cost:{project_id}:total          - str (float)  running total via INCRBYFLOAT
cost:{project_id}:sessions       - Set[str]     set of session_ids seen
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

import redis

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WARN_THRESHOLD: float = 0.8
"""Fraction of budget at which a warning state is reported."""

EXCEEDED_THRESHOLD: float = 1.0
"""Fraction of budget at which the budget is considered exceeded."""

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class BudgetState(str, Enum):
    """Budget consumption state relative to a limit."""

    OK = "ok"
    WARN = "warn"
    EXCEEDED = "exceeded"


@dataclass
class CostSnapshot:
    """Point-in-time cost snapshot for a session or project."""

    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CostSnapshot":
        """Deserialize from a dictionary (tolerant of extra keys)."""
        return cls(
            cost_usd=float(data.get("cost_usd", 0.0)),
            input_tokens=int(data.get("input_tokens", 0)),
            output_tokens=int(data.get("output_tokens", 0)),
            cached_tokens=int(data.get("cached_tokens", 0)),
            total_tokens=int(data.get("total_tokens", 0)),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_entry_id() -> str:
    """Return a random 16-byte hex string as a unique entry identifier."""
    return os.urandom(16).hex()


def _key_costs(project_id: str, session_id: str) -> str:
    """Redis key for the per-session append-only cost list."""
    return f"costs:{project_id}:{session_id}"


def _key_total(project_id: str) -> str:
    """Redis key for the project-wide running cost total."""
    return f"cost:{project_id}:total"


def _key_sessions(project_id: str) -> str:
    """Redis key for the set of session IDs belonging to a project."""
    return f"cost:{project_id}:sessions"


# ---------------------------------------------------------------------------
# CostLedger
# ---------------------------------------------------------------------------


class CostLedger:
    """Redis-backed append-only cost ledger.

    Parameters
    ----------
    redis_client : redis.Redis
        An already-connected ``redis.Redis`` (or compatible) instance.
        The caller is responsible for connection configuration; the ledger
        only issues data-plane commands.

    Example
    -------
    >>> import redis
    >>> r = redis.Redis(host="localhost", port=6379, decode_responses=True)
    >>> ledger = CostLedger(r)
    >>> ledger.record_run("proj-1", "sess-A", "gpt-4o", "agent", {
    ...     "cost_usd": 0.012,
    ...     "input_tokens": 1500,
    ...     "output_tokens": 400,
    ...     "cached_tokens": 800,
    ...     "total_tokens": 1900,
    ... })
    >>> ledger.is_budget_exceeded("proj-1", limit_usd=1.0)
    {'state': 'ok', 'spent': 0.012, 'limit': 1.0, 'ratio': 0.012}
    """

    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis: redis.Redis = redis_client

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def record_run(
        self,
        project_id: str,
        session_id: str,
        model: str,
        role: str,
        delta: Dict[str, Any],
    ) -> str:
        """Append a cost entry and update the running project total.

        This performs three Redis operations atomically enough for a cost
        ledger (RPUSH + INCRBYFLOAT + SADD).  A pipeline is used to reduce
        round-trips.

        Parameters
        ----------
        project_id : str
            Project identifier used in key prefixes.
        session_id : str
            Session identifier; scopes the append-only list.
        model : str
            Model name that produced this run (e.g. ``"gpt-4o"``).
        role : str
            Either ``"agent"`` or ``"subagent"``.
        delta : dict
            Must contain: ``cost_usd`` (float), ``input_tokens`` (int),
            ``output_tokens`` (int), ``cached_tokens`` (int),
            ``total_tokens`` (int).

        Returns
        -------
        str
            The generated ``entry_id`` for this record.

        Raises
        ------
        ValueError
            If *role* is not one of the accepted values or *delta* is
            missing required keys.
        """
        if role not in ("agent", "subagent"):
            raise ValueError(
                f"role must be 'agent' or 'subagent', got {role!r}"
            )

        required_keys = {
            "cost_usd",
            "input_tokens",
            "output_tokens",
            "cached_tokens",
            "total_tokens",
        }
        missing = required_keys - set(delta.keys())
        if missing:
            raise ValueError(f"delta is missing required keys: {missing}")

        entry_id = _generate_entry_id()
        entry = {
            "entry_id": entry_id,
            "timestamp": time.time(),
            "session_id": session_id,
            "model": model,
            "role": role,
            "cost_usd": float(delta["cost_usd"]),
            "input_tokens": int(delta["input_tokens"]),
            "output_tokens": int(delta["output_tokens"]),
            "cached_tokens": int(delta["cached_tokens"]),
            "total_tokens": int(delta["total_tokens"]),
        }

        pipe = self._redis.pipeline(transaction=False)
        pipe.rpush(_key_costs(project_id, session_id), json.dumps(entry))
        pipe.incrbyfloat(_key_total(project_id), float(delta["cost_usd"]))
        pipe.sadd(_key_sessions(project_id), session_id)
        pipe.execute()

        return entry_id

    # ------------------------------------------------------------------
    # Snapshot reconciliation
    # ------------------------------------------------------------------

    @staticmethod
    def snapshot_max(a: CostSnapshot, b: CostSnapshot) -> CostSnapshot:
        """Return the field-wise maximum of two CostSnapshot instances.

        This implements the *snapshotMax* reconciliation strategy from
        K-Dense BYOK: when two independent measurement paths (e.g. the
        agent's own counter and a subagent's reported cost) may diverge,
        taking the per-field maximum yields a safe upper-bound estimate
        that never under-counts.

        Parameters
        ----------
        a, b : CostSnapshot
            The two snapshots to reconcile.

        Returns
        -------
        CostSnapshot
            A new snapshot with each field set to ``max(a.field, b.field)``.
        """
        return CostSnapshot(
            cost_usd=max(a.cost_usd, b.cost_usd),
            input_tokens=max(a.input_tokens, b.input_tokens),
            output_tokens=max(a.output_tokens, b.output_tokens),
            cached_tokens=max(a.cached_tokens, b.cached_tokens),
            total_tokens=max(a.total_tokens, b.total_tokens),
        )

    # ------------------------------------------------------------------
    # Read path - budget
    # ------------------------------------------------------------------

    def is_budget_exceeded(
        self,
        project_id: str,
        limit_usd: float,
    ) -> Dict[str, Any]:
        """Check whether the project's running total exceeds its budget.

        This is an **O(1)** operation: it reads the single
        ``cost:{project_id}:total`` key maintained by ``INCRBYFLOAT``
        rather than scanning the append-only list.

        Parameters
        ----------
        project_id : str
            Project identifier.
        limit_usd : float
            The budget limit in USD.  Must be positive.

        Returns
        -------
        dict
            ``{"state": BudgetState, "spent": float, "limit": float,
            "ratio": float}``

            * ``"ok"``       -- spent < 80 % of limit
            * ``"warn"``     -- spent in [80 %, 100 %) of limit
            * ``"exceeded"`` -- spent >= 100 % of limit
        """
        raw = self._redis.get(_key_total(project_id))
        spent: float = float(raw) if raw is not None else 0.0

        if limit_usd <= 0:
            ratio = float("inf") if spent > 0 else 0.0
        else:
            ratio = spent / limit_usd

        if ratio >= EXCEEDED_THRESHOLD:
            state = BudgetState.EXCEEDED
        elif ratio >= WARN_THRESHOLD:
            state = BudgetState.WARN
        else:
            state = BudgetState.OK

        return {
            "state": state.value,
            "spent": spent,
            "limit": limit_usd,
            "ratio": ratio,
        }

    # ------------------------------------------------------------------
    # Read path - summaries
    # ------------------------------------------------------------------

    def session_summary(
        self,
        project_id: str,
        session_id: str,
    ) -> Dict[str, Any]:
        """Compute a cost summary for a single session, split by role.

        Iterates the append-only list once and aggregates entries into
        ``agent_usd`` and ``subagent_usd`` buckets.

        Parameters
        ----------
        project_id : str
            Project identifier.
        session_id : str
            Session identifier.

        Returns
        -------
        dict
            ``{
                "session_id": str,
                "agent_usd": float,
                "subagent_usd": float,
                "total_usd": float,
                "total_input_tokens": int,
                "total_output_tokens": int,
                "total_cached_tokens": int,
                "total_tokens": int,
                "entry_count": int,
            }``
        """
        raw_entries: List[bytes | str] = self._redis.lrange(
            _key_costs(project_id, session_id), 0, -1
        )

        agent_usd: float = 0.0
        subagent_usd: float = 0.0
        total_input: int = 0
        total_output: int = 0
        total_cached: int = 0
        total_tokens: int = 0
        count: int = 0

        for raw in raw_entries:
            entry: Dict[str, Any] = json.loads(raw)
            cost = float(entry.get("cost_usd", 0.0))
            role = entry.get("role", "agent")

            if role == "subagent":
                subagent_usd += cost
            else:
                agent_usd += cost

            total_input += int(entry.get("input_tokens", 0))
            total_output += int(entry.get("output_tokens", 0))
            total_cached += int(entry.get("cached_tokens", 0))
            total_tokens += int(entry.get("total_tokens", 0))
            count += 1

        return {
            "session_id": session_id,
            "agent_usd": agent_usd,
            "subagent_usd": subagent_usd,
            "total_usd": agent_usd + subagent_usd,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cached_tokens": total_cached,
            "total_tokens": total_tokens,
            "entry_count": count,
        }

    def project_summary(self, project_id: str) -> Dict[str, Any]:
        """Return the total cost across all sessions for a project.

        Uses the O(1) running total key for the USD figure, then iterates
        the session set to aggregate per-session snapshots for token
        breakdowns.

        Parameters
        ----------
        project_id : str
            Project identifier.

        Returns
        -------
        dict
            ``{
                "project_id": str,
                "total_usd": float,
                "session_count": int,
                "sessions": list[dict],   # per-session summaries
            }``
        """
        # O(1) authoritative total from the INCRBYFLOAT counter.
        raw_total = self._redis.get(_key_total(project_id))
        total_usd: float = float(raw_total) if raw_total is not None else 0.0

        session_ids: set = self._redis.smembers(_key_sessions(project_id))
        # smembers may return bytes or str depending on decode_responses.
        session_ids_decoded = {
            s.decode("utf-8") if isinstance(s, bytes) else s
            for s in session_ids
        }

        sessions: List[Dict[str, Any]] = []
        for sid in sorted(session_ids_decoded):
            sessions.append(self.session_summary(project_id, sid))

        return {
            "project_id": project_id,
            "total_usd": total_usd,
            "session_count": len(sessions),
            "sessions": sessions,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying Redis connection.

        Safe to call multiple times; subsequent calls are no-ops once the
        connection pool has been disconnected.
        """
        self._redis.close()

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<CostLedger redis={self._redis!r}>"
