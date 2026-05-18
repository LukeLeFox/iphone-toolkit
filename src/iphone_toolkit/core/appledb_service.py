from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


APPLEDB_BASE_URL = "https://appledb.dev"
CACHE_DIR = Path.home() / ".iphone-toolkit" / "cache"
CACHE_FILE = CACHE_DIR / "appledb_device_map.json"
CACHE_TTL_SECONDS = 7 * 24 * 60 * 60

DEVICE_SELECTION_PAGES = {
    "iPhone": "https://appledb.dev/device-selection/iPhone.html",
    "iPad": "https://appledb.dev/device-selection/iPad.html",
    "iPod": "https://appledb.dev/device-selection/iPod.html",
    "AppleTV": "https://appledb.dev/device-selection/AppleTV.html",
    "Watch": "https://appledb.dev/device-selection/AppleWatch.html",
}


@dataclass
class AppleDBDeviceLink:
    identifier: str
    name: str
    url: str
    source: str


def get_device_family(product_type: str) -> str | None:
    if product_type.startswith("iPhone"):
        return "iPhone"
    if product_type.startswith("iPad"):
        return "iPad"
    if product_type.startswith("iPod"):
        return "iPod"
    if product_type.startswith("AppleTV"):
        return "AppleTV"
    if product_type.startswith("Watch"):
        return "Watch"
    return None


def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}

    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

    created_at = float(data.get("created_at", 0))
    if time.time() - created_at > CACHE_TTL_SECONDS:
        return {}

    return data.get("devices", {})


def _save_cache(devices: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": time.time(),
        "devices": devices,
    }
    CACHE_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _download_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "iPhoneToolkit/0.1 (+https://github.com/LukeLeFox/iphone-toolkit)"
        },
    )

    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def _strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = unescape(value)
    return " ".join(value.split())


def _parse_device_selection_html(html: str, source_url: str) -> dict[str, dict[str, str]]:
    """
    Parse AppleDB device-selection pages.

    Expected structure is a repeated block containing:
      - an anchor to /device/<slug>.html
      - one or more identifiers like iPhone14,2

    The parser is intentionally dependency-free and tolerant.
    """
    devices: dict[str, dict[str, str]] = {}

    blocks = re.split(r"<hr[^>]*>|<\s*/?li[^>]*>\s*<hr", html, flags=re.IGNORECASE)

    # Fallback: AppleDB pages are also parseable as repeated h2/h3 sections.
    if len(blocks) < 3:
        blocks = re.split(r"(?=<a[^>]+href=[\"']/device/)", html, flags=re.IGNORECASE)

    for block in blocks:
        link_match = re.search(
            r'href=["\'](?P<href>/device/[^"\']+\.html?)["\'][^>]*>(?P<name>.*?)</a>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if not link_match:
            continue

        href = link_match.group("href")
        name = _strip_tags(link_match.group("name"))

        if not name or name.lower() == "view more":
            # Some blocks expose the name in the first device anchor and then
            # repeat "View more"; try all anchors and pick the first non-view-more.
            anchors = re.findall(
                r'href=["\'](?P<href>/device/[^"\']+\.html?)["\'][^>]*>(?P<name>.*?)</a>',
                block,
                flags=re.IGNORECASE | re.DOTALL,
            )
            for href_candidate, name_candidate in anchors:
                clean_name = _strip_tags(name_candidate)
                if clean_name and clean_name.lower() != "view more":
                    href = href_candidate
                    name = clean_name
                    break

        identifiers = set(re.findall(r"\b(?:iPhone|iPad|iPod|AppleTV|Watch)\d+,\d+\b", block))

        if not identifiers:
            continue

        url = APPLEDB_BASE_URL + href

        for identifier in identifiers:
            devices[identifier] = {
                "identifier": identifier,
                "name": name,
                "url": url,
                "source": source_url,
            }

    return devices


def refresh_device_map_for_family(family: str) -> dict[str, dict[str, str]]:
    if family not in DEVICE_SELECTION_PAGES:
        return {}

    source_url = DEVICE_SELECTION_PAGES[family]
    html = _download_text(source_url)
    return _parse_device_selection_html(html, source_url)


def get_appledb_device_link(product_type: str) -> AppleDBDeviceLink | None:
    product_type = product_type.strip()

    if not product_type:
        return None

    cached = _load_cache()
    if product_type in cached:
        item = cached[product_type]
        return AppleDBDeviceLink(
            identifier=item["identifier"],
            name=item["name"],
            url=item["url"],
            source=item.get("source", "cache"),
        )

    family = get_device_family(product_type)
    if not family:
        return None

    try:
        fresh = refresh_device_map_for_family(family)
    except URLError:
        return None
    except TimeoutError:
        return None
    except Exception:
        return None

    if fresh:
        cached.update(fresh)
        _save_cache(cached)

    if product_type not in cached:
        return None

    item = cached[product_type]
    return AppleDBDeviceLink(
        identifier=item["identifier"],
        name=item["name"],
        url=item["url"],
        source=item.get("source", DEVICE_SELECTION_PAGES.get(family, "")),
    )
