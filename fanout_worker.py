"""Run one media fanout cycle against Infrai queue."""

from media_fanout import AssetIngested, CreatorDelivery, FanoutService, InfraiQueue


def notify_creator(delivery: CreatorDelivery) -> bool:
    print(
        f"creator={delivery.creator_id} asset={delivery.asset_id} "
        f"rendition={delivery.rendition_uri}"
    )
    return True


def main() -> None:
    service = FanoutService(InfraiQueue())
    service.ingest(
        AssetIngested(
            asset_id="asset-2048",
            creator_id="creator-17",
            media_kind="video",
            source_uri="s3://media-inbox/asset-2048.mov",
        )
    )
    delivered = service.deliver_ready(notify_creator)
    print(f"acknowledged_deliveries={delivered}")


if __name__ == "__main__":
    main()
