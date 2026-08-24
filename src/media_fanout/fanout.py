"""Domain workflow: asset ingestion to processing and creator delivery."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AssetIngested:
    asset_id: str
    creator_id: str
    media_kind: str
    source_uri: str


@dataclass(frozen=True)
class CreatorDelivery:
    asset_id: str
    creator_id: str
    rendition_uri: str


class FanoutService:
    def __init__(self, queue: Any) -> None:
        self.queue = queue

    def ingest(self, request: AssetIngested) -> None:
        payload = {"event": "asset.ingested", **asdict(request)}
        self.queue.publish(payload, idempotency_key=f"asset:{request.asset_id}:ingested")

    def deliver_ready(
        self,
        deliver: Callable[[CreatorDelivery], bool],
        *,
        batch_size: int = 25,
    ) -> int:
        batch = self.queue.consume(max_messages=batch_size, visibility_timeout=60)
        delivered = 0
        for message in batch.get("messages", []):
            payload = message.get("payload", {})
            if payload.get("event") != "rendition.ready":
                continue
            request = CreatorDelivery(
                asset_id=payload["asset_id"],
                creator_id=payload["creator_id"],
                rendition_uri=payload["rendition_uri"],
            )
            if deliver(request):
                message_id = message["message_id"]
                self.queue.ack(message_id, idempotency_key=f"ack:{message_id}")
                delivered += 1
        return delivered
