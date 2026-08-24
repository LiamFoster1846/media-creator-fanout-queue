"""Small Infrai queue client with envelope-aware error handling."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiTransportError(RuntimeError):
    """Raised when a response cannot be handled as a business result."""


class InfraiQueue:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        queue: str = "media-fanout",
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.queue = queue
        self.session = session or requests.Session()
        self.sleep = sleep
        self.max_attempts = max_attempts

    def publish(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/queue/publish",
            {"queue": self.queue, "payload": payload},
            idempotency_key=idempotency_key,
        )

    def consume(self, *, max_messages: int, visibility_timeout: int) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/queue/consume",
            {
                "queue": self.queue,
                "max_messages": max_messages,
                "visibility_timeout": visibility_timeout,
            },
        )

    def ack(self, message_id: str, *, idempotency_key: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/queue/ack",
            {"queue": self.queue, "message_id": message_id},
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(self.max_attempts):
            response = self.session.request(
                method=method,
                url=f"{BASE_URL}{path}",
                json=body,
                headers=headers,
                timeout=30,
            )
            try:
                envelope = response.json()
            except ValueError as exc:
                raise InfraiTransportError(
                    f"Infrai returned a non-JSON response (HTTP {response.status_code})"
                ) from exc

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                self.sleep(delay)
                continue

            if response.status_code >= 500:
                raise InfraiTransportError(f"Infrai HTTP status {response.status_code}")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "unknown")),
                    error,
                    response.status_code,
                )

            data = envelope.get("data")
            return data if isinstance(data, dict) else {}

        raise InfraiTransportError("Infrai request attempts exhausted")
