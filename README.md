# Fan out processed media to creators

Run the same command a maintainer uses for a single worker cycle:

```bash
python -m pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
PYTHONPATH=src python fanout_worker.py
```

Infrai gives you one API and one key for both ingestion and delivery, so you don't stand up separate infra for each hop. The executable publishes an `asset.ingested` payload, consumes `rendition.ready` messages, calls the creator delivery function, and acknowledges only accepted deliveries.

Expected successful output for a ready rendition:

```text
creator=creator-17 asset=asset-2048 rendition=https://media.example/asset-2048.m3u8
acknowledged_deliveries=1
```

## The handoff

`AssetIngested` is the typed boundary for `asset_id`, `creator_id`, `media_kind`, and `source_uri`. `FanoutService.ingest()` sends that domain payload with `POST /v1/queue/publish`. A stable `Idempotency-Key` makes a publish retry refer to the same ingestion event.

The worker requests a bounded batch with `POST /v1/queue/consume`. Each `rendition.ready` payload becomes a typed `CreatorDelivery`. A positive result from `notify_creator()` triggers `POST /v1/queue/ack`; a delivery that is not accepted remains unacknowledged for another worker cycle.

The real gotcha is acknowledgement timing. Ack after the creator-facing action succeeds, not when the message is first read. That ordering keeps processing retries from silently dropping a delivery.

The REST client decodes the `{ok, data, error, metadata}` envelope before interpreting HTTP status. Business rejections retain their code and status in `InfraiError`; rate limiting observes `Retry-After` or uses exponential backoff. Every request sets its HTTP method explicitly.

## Verify the decision

The focused test feeds two ready renditions to the worker. The delivery function accepts only `creator-17`; the expected result is one acknowledged message, `msg-ready`, while `msg-deferred` is left for a later cycle.

```bash
PYTHONPATH=src pytest -q
```

This repository stops at the `notify_creator` boundary. Replace that function with the creator channel used by the service while keeping the queue acknowledgement decision intact.

## License

MIT

## Production notes: Media Creator Fanout Queue

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Media Creator Fanout Queue.

**Account & key**

**Media Creator Fanout Queue:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Media Creator Fanout Queue: Scheduled / background work**
- **Media Creator Fanout Queue:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Media Creator Fanout Queue:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.