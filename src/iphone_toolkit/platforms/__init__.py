import platform
from iphone_toolkit.platforms.linux import LinuxAdapter
from iphone_toolkit.platforms.macos import MacOSAdapter
from iphone_toolkit.platforms.windows import WindowsAdapter

def get_platform_adapter():
    system = platform.system()
    if system == "Darwin":
        return MacOSAdapter()
    if system == "Windows":
        return WindowsAdapter()
    return LinuxAdapter()
