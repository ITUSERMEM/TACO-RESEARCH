"""ExperimentTemplateLib — Code reuse across experiments.

Stores, retrieves, and recommends experiment templates
based on task type and previous usage patterns.
"""

import json
import time
from typing import Optional

from redis import Redis

TEMPLATE_KEY = "experiment:templates"
TEMPLATE_USAGE_KEY = "experiment:template_usage"


class ExperimentTemplateLib:
    """Library of reusable experiment templates.

    Each template has:
    - id: unique identifier
    - name: human-readable name
    - task_type: classification / regression / generation / etc.
    - framework: pytorch / tensorflow / jax
    - code: template code with {{placeholders}}
    - tags: for retrieval
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.r = Redis.from_url(redis_url, decode_responses=True)

    def add_template(self, name: str, task_type: str, framework: str,
                     code: str, tags: Optional[list[str]] = None) -> str:
        """Store an experiment template."""
        template_id = f"tpl-{int(time.time())}"
        template = {
            "id": template_id,
            "name": name,
            "task_type": task_type,
            "framework": framework,
            "code": code,
            "tags": tags or [],
            "usage_count": 0,
            "created_at": time.time(),
        }
        self.r.hset(TEMPLATE_KEY, template_id, json.dumps(template))
        return template_id

    def get_template(self, template_id: str) -> Optional[dict]:
        raw = self.r.hget(TEMPLATE_KEY, template_id)
        if not raw:
            return None
        return json.loads(raw)

    def recommend(self, task_type: str, framework: str = "") -> list[dict]:
        """Recommend templates based on task type and framework."""
        templates = []
        for key in self.r.hkeys(TEMPLATE_KEY):
            try:
                tpl = json.loads(self.r.hget(TEMPLATE_KEY, key))
                if tpl.get("task_type") == task_type:
                    if not framework or tpl.get("framework") == framework:
                        templates.append(tpl)
            except (json.JSONDecodeError, TypeError):
                continue
        return sorted(templates, key=lambda t: t.get("usage_count", 0), reverse=True)

    def record_usage(self, template_id: str):
        """Increment usage counter for a template."""
        self.r.hincrby(TEMPLATE_USAGE_KEY, template_id, 1)
        tpl = self.get_template(template_id)
        if tpl:
            tpl["usage_count"] = tpl.get("usage_count", 0) + 1
            self.r.hset(TEMPLATE_KEY, template_id, json.dumps(tpl))

    def add_default_templates(self):
        """Seed the library with common ML experiment templates."""
        templates = [
            {
                "name": "PyTorch Classification",
                "task_type": "classification",
                "framework": "pytorch",
                "code": """import torch
import torch.nn as nn

class Model(nn.Module):
    def __init__(self, input_dim={{input_dim}}, hidden_dim={{hidden_dim}}, num_classes={{num_classes}}):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, x):
        return self.net(x)
""",
                "tags": ["classification", "mlp", "pytorch"],
            },
            {
                "name": "CNN 1D for Time Series",
                "task_type": "classification",
                "framework": "pytorch",
                "code": """import torch.nn as nn

class CNN1D(nn.Module):
    def __init__(self, in_channels={{in_channels}}, num_classes={{num_classes}}):
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, 64, kernel_size=3)
        self.conv2 = nn.Conv1d(64, 128, kernel_size=3)
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Linear(128, num_classes)

    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.pool(x).squeeze(-1)
        return self.fc(x)
""",
                "tags": ["cnn", "timeseries", "1d"],
            },
        ]
        for t in templates:
            self.add_template(**t)
