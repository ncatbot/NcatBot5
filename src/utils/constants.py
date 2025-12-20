from typing import Final, Literal

from ..plugins_system import EventBus, SimpleEventBus

DEBUG = True
ProtocolName = Literal["napcat"]


class DefaultSetting:
    debug: Final[bool] = DEBUG
    event_bus: Final[EventBus] = SimpleEventBus()

    def __init__(self) -> None:
        raise RuntimeError("DefaultSetting 不允许实例化，请直接通过类访问属性")
