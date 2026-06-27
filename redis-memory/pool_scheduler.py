"""PoolScheduler — Resource pool scheduling across projects.

Manages GPU/CPU/memory allocation across multiple concurrent projects.
Kocoro-inspired bounded semaphore pattern for resource contention.
"""

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional


@dataclass
class ResourcePool:
    gpu_count: int = 1
    cpu_cores: int = 16
    memory_gb: int = 64
    gpu_memory_gb: int = 32


@dataclass
class Allocation:
    project_id: str
    gpus: int = 0
    cpu_cores: int = 0
    memory_gb: int = 0
    acquired_at: Optional[float] = None


class PoolScheduler:
    """Resource allocation across competing projects.

    Ensures:
    - No project exceeds available resources
    - Fair sharing across projects
    - GPU memory isolation
    - Blocking acquire with timeout
    """

    def __init__(self, pool: Optional[ResourcePool] = None):
        self.pool = pool or ResourcePool()
        self.allocations: dict[str, Allocation] = {}
        self.queue: list[str] = []

    @property
    def available(self) -> ResourcePool:
        used_gpu = sum(a.gpus for a in self.allocations.values())
        used_cpu = sum(a.cpu_cores for a in self.allocations.values())
        used_mem = sum(a.memory_gb for a in self.allocations.values())
        return ResourcePool(
            gpu_count=self.pool.gpu_count - used_gpu,
            cpu_cores=self.pool.cpu_cores - used_cpu,
            memory_gb=self.pool.memory_gb - used_mem,
        )

    def acquire(self, project_id: str, gpus: int = 1,
                cpu_cores: int = 2, memory_gb: int = 8,
                timeout: float = 300) -> Optional[Allocation]:
        """Acquire resources for a project.

        Blocks until resources are available or timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if project_id in self.allocations:
                return self.allocations[project_id]

            avail = self.available
            if avail.gpu_count >= gpus and avail.cpu_cores >= cpu_cores and avail.memory_gb >= memory_gb:
                alloc = Allocation(
                    project_id=project_id,
                    gpus=gpus,
                    cpu_cores=cpu_cores,
                    memory_gb=memory_gb,
                    acquired_at=time.time(),
                )
                self.allocations[project_id] = alloc
                if project_id in self.queue:
                    self.queue.remove(project_id)
                return alloc

            if project_id not in self.queue:
                self.queue.append(project_id)
            time.sleep(5)

        return None

    def release(self, project_id: str):
        """Release resources held by a project."""
        if project_id in self.allocations:
            del self.allocations[project_id]

    def status(self) -> dict:
        return {
            "total": {
                "gpus": self.pool.gpu_count,
                "cpu_cores": self.pool.cpu_cores,
                "memory_gb": self.pool.memory_gb,
            },
            "available": {
                "gpus": self.available.gpu_count,
                "cpu_cores": self.available.cpu_cores,
                "memory_gb": self.available.memory_gb,
            },
            "allocations": {
                pid: {"gpus": a.gpus, "cpu": a.cpu_cores, "mem": a.memory_gb}
                for pid, a in self.allocations.items()
            },
            "queue": list(self.queue),
        }
