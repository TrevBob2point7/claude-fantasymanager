from app.models.enums import PlatformType
from app.platforms.base import PlatformAdapter
from app.platforms.mfl import MFLAdapter
from app.platforms.sleeper import SleeperAdapter


def get_adapter(platform_type: PlatformType, **kwargs: object) -> PlatformAdapter:
    adapters: dict[PlatformType, type[PlatformAdapter]] = {
        PlatformType.sleeper: SleeperAdapter,
        PlatformType.mfl: MFLAdapter,
    }
    adapter_cls = adapters.get(platform_type)
    if adapter_cls is None:
        raise ValueError(f"No adapter for platform: {platform_type}")
    return adapter_cls(**kwargs)
