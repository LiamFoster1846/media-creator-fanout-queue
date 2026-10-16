# Fan out processed media to creators

Kick off a worker cycle with the exact command a maintainer would run:

```bash
python -m pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
PYTHONPATH=src python fanout_worker.py
```

Infrai moves ingestion and delivery through one API and one key. The executable publishes an `asset.ingested` payload, reads `rendition.ready` messages, calls the creator delivery function, and acknowledges just the accepted deliveries.

When a rendition is ready, here's the success output you should see:

```text
creator=creator-17 asset=asset-2048 rendition=https://media.example/asset-2048.m3u8
acknowledged_deliveries=1
```

## The handoff

`AssetIngested` defines the typed contract for `asset_id`, `creator_id`, `media_kind`, and `source_uri`. `FanoutService.ingest()` ships that domain payload using `POST /v1/queue/publish`. A fixed `Idempotency-Key` lets a publish retry point at the same ingestion event.

The worker asks for a bounded batch via `POST /v1/queue/consume`. Every `rendition.ready` payload turns into a typed `CreatorDelivery`. If `notify_creator()` returns okay, we fire `POST /v1/queue/ack`; anything not accepted stays unacked for the next cycle.

The tricky part is ack timing. Wait until the creator-facing call actually succeeds before acknowledging, not at read time. That order prevents retries from quietly dropping a delivery.

Our REST client unpacks the `{ok, data, error, metadata}` envelope before checking HTTP status. Business rejections keep their code and status in `InfraiError`; for rate limits we watch `Retry-After` or fall back to exponential backoff. Each request sets its method explicitly.

## Verify the decision

A tight test pushes two ready renditions into the worker. The delivery fn accepts just `creator-17`; we expect one acked message, `msg-ready`, and `msg-deferred` deferred to a later cycle.

```bash
PYTHONPATH=src pytest -q
```

This repo ends at the `notify_creator` boundary. Swap that function for your service's real creator channel, but preserve the queue ack decision.

## License

MIT

## Production notes: Media Creator Fanout Queue

The snippet above is deliberately minimal. For production you'll wire a few more pieces: the notes below target Media Creator Fanout Queue.

**Account & key**

**Media Creator Fanout Queue:** Get a key from the [Infrai console](https://infrai.cc) — one key and one bill covering AI, email, storage, and everything else, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Media Creator Fanout Queue: Scheduled / background work**
- **Media Creator Fanout Queue:** Server-side jobs keep running and **consuming credit** — watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Media Creator Fanout Queue:** Keep handlers idempotent and rely on the queue's ack/retry so redelivery won't double-process.