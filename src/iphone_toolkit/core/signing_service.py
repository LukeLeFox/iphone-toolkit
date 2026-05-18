from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass
class SigningStatus:
    product_type: str
    version: str | None
    build: str | None
    signed: bool | None
    matched: bool
    source: str
    url: str | None = None
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.matched and self.signed is True

    @property
    def unsigned(self) -> bool:
        return self.matched and self.signed is False

    @property
    def unknown(self) -> bool:
        return not self.matched or self.signed is None

    def summary(self) -> str:
        version = self.version or "versione sconosciuta"
        build = self.build or "build sconosciuta"

        if self.ok:
            return f"SIGNED - {self.product_type} / iOS {version} ({build})"

        if self.unsigned:
            return f"UNSIGNED - {self.product_type} / iOS {version} ({build})"

        if self.message:
            return f"UNKNOWN - {self.message}"

        return f"UNKNOWN - firma non determinabile per {self.product_type} / iOS {version} ({build})"


def _download_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": "iPhoneToolkit/0.1 (+https://github.com/LukeLeFox/iphone-toolkit)"
        },
    )

    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def check_ipsw_me_signing_status(
    product_type: str,
    version: str | None,
    build: str | None,
) -> SigningStatus:
    """
    Check signing status using ipsw.me public API.

    The API is not Apple itself, so this is a pre-flight helper.
    idevicerestore/TSS remains the final source of truth during restore.
    """
    product_type = (product_type or "").strip()
    version = (version or "").strip() or None
    build = (build or "").strip() or None

    if not product_type or product_type == "-":
        return SigningStatus(
            product_type=product_type or "-",
            version=version,
            build=build,
            signed=None,
            matched=False,
            source="ipsw.me",
            message="ProductType non rilevato",
        )

    if not version and not build:
        return SigningStatus(
            product_type=product_type,
            version=version,
            build=build,
            signed=None,
            matched=False,
            source="ipsw.me",
            message="version/build IPSW non rilevati",
        )

    url = f"https://api.ipsw.me/v4/device/{quote(product_type)}?type=ipsw"

    try:
        payload = _download_json(url)
    except HTTPError as exc:
        return SigningStatus(
            product_type=product_type,
            version=version,
            build=build,
            signed=None,
            matched=False,
            source="ipsw.me",
            message=f"HTTP error API signing: {exc.code}",
        )
    except URLError as exc:
        return SigningStatus(
            product_type=product_type,
            version=version,
            build=build,
            signed=None,
            matched=False,
            source="ipsw.me",
            message=f"errore rete API signing: {exc.reason}",
        )
    except Exception as exc:
        return SigningStatus(
            product_type=product_type,
            version=version,
            build=build,
            signed=None,
            matched=False,
            source="ipsw.me",
            message=f"errore API signing: {exc}",
        )

    firmwares = payload.get("firmwares", [])

    if not isinstance(firmwares, list):
        return SigningStatus(
            product_type=product_type,
            version=version,
            build=build,
            signed=None,
            matched=False,
            source="ipsw.me",
            message="risposta API non valida: firmwares mancante",
        )

    # Prefer exact build match, because version alone can be ambiguous.
    for fw in firmwares:
        if not isinstance(fw, dict):
            continue

        fw_build = str(fw.get("buildid", "")).strip()
        fw_version = str(fw.get("version", "")).strip()

        if build and fw_build == build:
            return SigningStatus(
                product_type=product_type,
                version=fw_version or version,
                build=fw_build or build,
                signed=bool(fw.get("signed")),
                matched=True,
                source="ipsw.me",
                url=fw.get("url"),
            )

    # Fallback to version match.
    for fw in firmwares:
        if not isinstance(fw, dict):
            continue

        fw_build = str(fw.get("buildid", "")).strip()
        fw_version = str(fw.get("version", "")).strip()

        if version and fw_version == version:
            return SigningStatus(
                product_type=product_type,
                version=fw_version or version,
                build=fw_build or build,
                signed=bool(fw.get("signed")),
                matched=True,
                source="ipsw.me",
                url=fw.get("url"),
            )

    return SigningStatus(
        product_type=product_type,
        version=version,
        build=build,
        signed=None,
        matched=False,
        source="ipsw.me",
        message="firmware non trovato nella lista API per questo ProductType",
    )
