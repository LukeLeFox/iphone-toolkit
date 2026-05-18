from __future__ import annotations

import plistlib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IPSWAnalysis:
    path: str
    size_bytes: int = 0
    product_version: str | None = None
    product_build_version: str | None = None
    supported_product_types: list[str] = field(default_factory=list)
    device_classes: list[str] = field(default_factory=list)
    build_manifest_found: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024 ** 3)

    @property
    def ok(self) -> bool:
        return self.build_manifest_found and not self.errors

    def supports_product_type(self, product_type: str | None) -> bool | None:
        if not product_type or product_type == "-":
            return None

        if not self.supported_product_types:
            return None

        return product_type in self.supported_product_types

    def short_summary(self, product_type: str | None = None) -> str:
        parts: list[str] = []

        if self.product_version:
            parts.append(f"iOS {self.product_version}")

        if self.product_build_version:
            parts.append(f"build {self.product_build_version}")

        if self.supported_product_types:
            parts.append(f"{len(self.supported_product_types)} ProductType supportati")

        compatibility = self.supports_product_type(product_type)

        if compatibility is True:
            parts.append(f"compatibile con {product_type}")
        elif compatibility is False:
            parts.append(f"NON compatibile con {product_type}")
        elif product_type:
            parts.append(f"compatibilità con {product_type} non determinabile")

        if not parts:
            parts.append("IPSW analizzato")

        return " - ".join(parts)


def _find_build_manifest(names: list[str]) -> str | None:
    for name in names:
        if name == "BuildManifest.plist":
            return name

    for name in names:
        if name.endswith("/BuildManifest.plist"):
            return name

    return None


def _normalize_string_list(values) -> list[str]:
    if not isinstance(values, list):
        return []

    clean: list[str] = []

    for item in values:
        if isinstance(item, str) and item.strip():
            clean.append(item.strip())

    return sorted(set(clean))


def _extract_device_classes(build_manifest: dict) -> list[str]:
    values: set[str] = set()

    identities = build_manifest.get("BuildIdentities", [])

    if not isinstance(identities, list):
        return []

    for identity in identities:
        if not isinstance(identity, dict):
            continue

        info = identity.get("Info", {})
        if not isinstance(info, dict):
            continue

        device_class = info.get("DeviceClass")
        if isinstance(device_class, str) and device_class.strip():
            values.add(device_class.strip())

    return sorted(values)


def analyze_ipsw(path: str) -> IPSWAnalysis:
    ipsw_path = Path(path).expanduser()

    analysis = IPSWAnalysis(path=str(ipsw_path))

    if not ipsw_path.exists():
        analysis.errors.append(f"File non trovato: {ipsw_path}")
        return analysis

    if not ipsw_path.is_file():
        analysis.errors.append(f"Il percorso non è un file: {ipsw_path}")
        return analysis

    if ipsw_path.suffix.lower() != ".ipsw":
        analysis.errors.append("Il file non ha estensione .ipsw")
        return analysis

    analysis.size_bytes = ipsw_path.stat().st_size

    try:
        with zipfile.ZipFile(ipsw_path, "r") as archive:
            manifest_name = _find_build_manifest(archive.namelist())

            if manifest_name is None:
                analysis.errors.append("BuildManifest.plist non trovato nell'IPSW")
                return analysis

            analysis.build_manifest_found = True

            with archive.open(manifest_name) as manifest_file:
                build_manifest = plistlib.load(manifest_file)

    except zipfile.BadZipFile:
        analysis.errors.append("File IPSW non leggibile: archivio ZIP non valido")
        return analysis
    except Exception as exc:
        analysis.errors.append(f"Errore lettura IPSW: {exc}")
        return analysis

    if not isinstance(build_manifest, dict):
        analysis.errors.append("BuildManifest.plist non contiene un dizionario valido")
        return analysis

    product_version = build_manifest.get("ProductVersion")
    product_build_version = build_manifest.get("ProductBuildVersion")

    if isinstance(product_version, str):
        analysis.product_version = product_version

    if isinstance(product_build_version, str):
        analysis.product_build_version = product_build_version

    analysis.supported_product_types = _normalize_string_list(
        build_manifest.get("SupportedProductTypes")
    )

    analysis.device_classes = _extract_device_classes(build_manifest)

    return analysis


def format_ipsw_analysis(analysis: IPSWAnalysis, product_type: str | None = None) -> str:
    lines: list[str] = []

    lines.append("=== IPSW ANALYSIS ===")
    lines.append(f"File: {analysis.path}")
    lines.append(f"Size: {analysis.size_gb:.2f} GB")

    if analysis.product_version:
        lines.append(f"iOS version: {analysis.product_version}")
    else:
        lines.append("iOS version: non rilevata")

    if analysis.product_build_version:
        lines.append(f"Build: {analysis.product_build_version}")
    else:
        lines.append("Build: non rilevata")

    lines.append(f"BuildManifest.plist: {'presente' if analysis.build_manifest_found else 'non trovato'}")

    if analysis.device_classes:
        lines.append("Device classes:")
        for item in analysis.device_classes:
            lines.append(f"  - {item}")

    if analysis.supported_product_types:
        lines.append("Supported ProductTypes:")
        for item in analysis.supported_product_types:
            prefix = "  -"
            if product_type and item == product_type:
                prefix = "  ✓"
            lines.append(f"{prefix} {item}")
    else:
        lines.append("Supported ProductTypes: non rilevati")

    if product_type and product_type != "-":
        compatibility = analysis.supports_product_type(product_type)

        if compatibility is True:
            lines.append(f"Compatibility: OK, IPSW compatibile con {product_type}")
        elif compatibility is False:
            lines.append(f"Compatibility: ERRORE, IPSW NON compatibile con {product_type}")
        else:
            lines.append(f"Compatibility: non determinabile per {product_type}")
    else:
        lines.append("Compatibility: ProductType del device non rilevato")

    if analysis.errors:
        lines.append("Errors:")
        for error in analysis.errors:
            lines.append(f"  - {error}")

    lines.append("Signing: verifica online separata tramite Pre-flight / Analizza IPSW")
    lines.append("=== END IPSW ANALYSIS ===")

    return "\n".join(lines)
