from __future__ import annotations
from abc import ABC, abstractmethod

class PlatformAdapter(ABC):
    @abstractmethod
    def open_file_manager(self, path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def open_device_ui_hint(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def platform_name(self) -> str:
        raise NotImplementedError
