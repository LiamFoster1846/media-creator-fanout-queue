from typing import Any

from media_fanout import AssetIngested, FanoutService


class RecordingQueue:
    def __init__(self) -> None:
        self.published: list[tuple[dict[str, Any], str]] = []
        self.acked: list[tuple[str, str]] = []

    def publish(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        self.published.append((payload, idempotency_key))
        return {}

    def consume(self, *, max_messages: int, visibility_timeout: int) -> dict[str, Any]:
        assert (max_messages, visibility_timeout) == (25, 60)
        return {
            "messages": [
                {
                    "message_id": "msg-ready",
                    "payload": {
                        "event": "rendition.ready",
                        "asset_id": "asset-2048",
                        "creator_id": "creator-17",
                        "rendition_uri": "https://media.example/asset-2048.m3u8",
                    },
                },
                {
                    "message_id": "msg-deferred",
                    "payload": {
                        "event": "rendition.ready",
                        "asset_id": "asset-4096",
                        "creator_id": "creator-23",
                        "rendition_uri": "https://media.example/asset-4096.m3u8",
                    },
                },
            ]
        }

    def ack(self, message_id: str, *, idempotency_key: str) -> dict[str, Any]:
        self.acked.append((message_id, idempotency_key))
        return {}


def test_ingestion_handoff_and_ack_only_after_creator_delivery() -> None:
    queue = RecordingQueue()
    service = FanoutService(queue)
    service.ingest(AssetIngested("asset-2048", "creator-17", "video", "s3://inbox/a.mov"))

    delivered = service.deliver_ready(lambda request: request.creator_id == "creator-17")

    payload, key = queue.published[0]
    assert payload["event"] == "asset.ingested"
    assert payload["asset_id"] == "asset-2048"
    assert key == "asset:asset-2048:ingested"
    assert delivered == 1
    assert queue.acked == [("msg-ready", "ack:msg-ready")]
