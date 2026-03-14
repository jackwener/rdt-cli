"""Runtime configuration for transport, auth, and anti-detection defaults."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeConfig:
    """Normalized runtime config used by transports and session validation."""

    timeout: float = 30.0
    read_request_delay: float = 1.0
    write_request_delay: float = 2.5
    max_retries: int = 3
    status_check_timeout: float = 10.0


DEFAULT_CONFIG = RuntimeConfig()
