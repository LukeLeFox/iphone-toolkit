import subprocess
from iphone_toolkit.platforms.base import PlatformAdapter

class MacOSAdapter(PlatformAdapter):
    def open_file_manager(self, path: str) -> None:
        subprocess.run(["open", path], check=False)

    def open_device_ui_hint(self) -> None:
        subprocess.run(["open", "/System/Library/CoreServices/Finder.app"], check=False)

    def platform_name(self) -> str:
        return "macOS"
