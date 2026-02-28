from app.models.enums import PlatformType
from app.platforms.base import PlatformAdapter
from app.platforms.sleeper import SleeperAdapter


def get_adapter(platform_type: PlatformType) -> PlatformAdapter:
    adapters: dict[PlatformType, type[PlatformAdapter]] = {
        PlatformType.sleeper: SleeperAdapter,
    }
    adapter_cls = adapters.get(platform_type)
    if adapter_cls is None:
        raise ValueError(f"No adapter for platform: {platform_type}")
    return adapter_cls()
