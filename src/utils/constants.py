from pathlib import Path
from typing import Final, Literal, Tuple

from ..plugins_system import EventBus, SimpleEventBus

DEBUG = True
base_path = Path(__file__).resolve()
ProtocolName = Literal["napcat"]


class DefaultSetting:
    debug: Final[bool] = DEBUG

    sys_plugins: Tuple[Path] = (base_path.parent / "sys_plugin",)
    event_bus: Final[EventBus] = SimpleEventBus()

    def __init__(self) -> None:
        raise RuntimeError("DefaultSetting 不允许实例化，请直接通过类访问属性")
