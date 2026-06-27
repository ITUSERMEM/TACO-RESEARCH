"""ParallelExecutor — Kocoro-inspired parallel tool execution.

Groups independent tool calls into batches and executes them concurrently:
- Read-only tools execute in parallel within a batch
- Write tools execute serially (dependency ordering)
- Each batch completes before the next starts
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

READ_LIKE_TOOLS = {
    "search", "get", "list", "read", "find", "lookup", "query",
    "check", "status", "show", "describe", "log", "logs",
    "file_read", "paper_search", "semantic_scholar",
}


class ParallelExecutor:
    """Execute tool calls in parallel batches.

    Usage:
        executor = ParallelExecutor(max_workers=4)
        results = executor.execute_all(tool_calls)
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def execute_all(self, tool_calls: list[dict],
                    execute_fn, permissions=None) -> list[dict]:
        """Group and execute all tool calls.

        Args:
            tool_calls: list of {"name": str, "args": dict, "id": str, ...}
            execute_fn: callable (tool_name, args) -> result dict
            permissions: optional PermissionSystem instance

        Returns:
            list of {"call_id": str, "result": dict, "elapsed_ms": int}
        """
        batches = self._group_into_batches(tool_calls)
        all_results = []

        for batch in batches:
            batch_results = self._execute_batch(batch, execute_fn, permissions)
            all_results.extend(batch_results)

        return all_results

    def _group_into_batches(self, tool_calls: list[dict]) -> list[list[dict]]:
        """Group tool calls: read-only tools together, writes solo."""
        batches = []
        current_read_batch = []

        for call in tool_calls:
            name = call.get("name", "")

            if self._is_read_only(name):
                current_read_batch.append(call)
            else:
                if current_read_batch:
                    batches.append(current_read_batch)
                    current_read_batch = []
                batches.append([call])

        if current_read_batch:
            batches.append(current_read_batch)

        return batches

    def _execute_batch(self, batch: list[dict], execute_fn, permissions=None) -> list[dict]:
        """Execute a batch: parallel for read-only, serial for single write."""
        if len(batch) == 1:
            call = batch[0]
            start = time.time()
            try:
                result = execute_fn(call["name"], call.get("args", {}), permissions)
                elapsed = int((time.time() - start) * 1000)
            except Exception as e:
                result = {"error": str(e)}
                elapsed = 0
            return [{"call_id": call.get("id", ""), "result": result, "elapsed_ms": elapsed}]

        # Parallel execution for read-only batch
        futures = {}
        for call in batch:
            future = self._executor.submit(
                self._safe_execute, execute_fn, call, permissions
            )
            futures[future] = call

        results = []
        for future in as_completed(futures):
            call = futures[future]
            try:
                result_data = future.result()
            except Exception as e:
                result_data = {"error": str(e), "elapsed_ms": 0}
            results.append(result_data)

        results.sort(key=lambda r: r.get("elapsed_ms", 0))
        return results

    @staticmethod
    def _safe_execute(execute_fn, call: dict, permissions) -> dict:
        start = time.time()
        try:
            result = execute_fn(call["name"], call.get("args", {}), permissions)
            elapsed = int((time.time() - start) * 1000)
        except Exception as e:
            result = {"error": str(e)}
            elapsed = 0
        return {"call_id": call.get("id", ""), "result": result, "elapsed_ms": elapsed}

    @staticmethod
    def _is_read_only(tool_name: str) -> bool:
        return tool_name in READ_LIKE_TOOLS or any(
            tool_name.startswith(prefix) for prefix in ["get_", "read_", "list_", "search_"]
        )

    def shutdown(self):
        self._executor.shutdown(wait=True)
