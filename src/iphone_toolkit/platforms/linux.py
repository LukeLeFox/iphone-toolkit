import subprocess
from iphone_toolkit.platforms.base import PlatformAdapter

class LinuxAdapter(PlatformAdapter):
    def open_file_manager(self, path: str) -> None:
        subprocess.run(["xdg-open", path], check=False)

    def open_device_ui_hint(self) -> None:
        subprocess.run(["xdg-open", "."], check=False)

    def platform_name(self) -> str:
        return "Linux"
