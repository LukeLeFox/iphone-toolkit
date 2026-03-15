import os
import subprocess
from iphone_toolkit.platforms.base import PlatformAdapter

class WindowsAdapter(PlatformAdapter):
    def open_file_manager(self, path: str) -> None:
        os.startfile(path)

    def open_device_ui_hint(self) -> None:
        subprocess.run(["explorer.exe"], check=False)

    def platform_name(self) -> str:
        return "Windows"
