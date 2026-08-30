"""Cached boto3 clients with explicit timeouts and adaptive retries.

Clients are created once per container and reused. The default botocore read
timeout is 60s, which is longer than several of our Lambda timeouts — leaving it
alone means the function gets killed before botocore can report anything useful,
so every client here sets one explicitly.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import boto3
from botocore.config import Config

_clients: Dict[Tuple[str, int, int], Any] = {}
_resources: Dict[str, Any] = {}


def _config(read_timeout: int, max_attempts: int) -> Config:
    return Config(
        connect_timeout=5,
        read_timeout=read_timeout,
        retries={"max_attempts": max_attempts, "mode": "adaptive"},
        user_agent_extra="aegis-swarm",
    )


def client(service: str, read_timeout: int = 20, max_attempts: int = 3) -> Any:
    key = (service, read_timeout, max_attempts)
    if key not in _clients:
        _clients[key] = boto3.client(service, config=_config(read_timeout, max_attempts))
    return _clients[key]


def dynamodb_table(name: str) -> Any:
    if name not in _resources:
        resource = boto3.resource("dynamodb", config=_config(read_timeout=10, max_attempts=5))
        _resources[name] = resource.Table(name)
    return _resources[name]
