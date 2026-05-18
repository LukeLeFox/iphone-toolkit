from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from iphone_toolkit.core.firmware_service import get_log_dir, validate_ipsw
from iphone_toolkit.core.ipsw_service import analyze_ipsw
from iphone_toolkit.core.signing_service import check_ipsw_me_signing_status


@dataclass
class PreflightCheck:
    name: str
    status: str
    message: str

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def warn(self) -> bool:
        return self.status == "warn"

    @property
    def fail(self) -> bool:
        return self.status == "fail"

    def to_line(self) -> str:
        icon = {
            "ok": "✓",
            "warn": "!",
            "fail": "✗",
        }.get(self.status, "?")

        return f"{icon} {self.name}: {self.message}"


def _check_command(command: str, required: bool = True) -> PreflightCheck:
    if shutil.which(command):
        return PreflightCheck(command, "ok", "presente")

    if required:
        return PreflightCheck(command, "fail", "mancante")

    return PreflightCheck(command, "warn", "mancante, funzione opzionale non disponibile")


def _check_log_dir() -> PreflightCheck:
    try:
        log_dir = get_log_dir()
        test_file = log_dir / ".write-test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return PreflightCheck("Cartella log", "ok", f"scrivibile: {log_dir}")
    except Exception as exc:
        return PreflightCheck("Cartella log", "fail", f"non scrivibile: {exc}")


def _check_ipsw_file(ipsw_path: str) -> PreflightCheck:
    valid, message = validate_ipsw(ipsw_path)

    if not valid:
        return PreflightCheck("IPSW file", "fail", message)

    size_gb = Path(message).stat().st_size / (1024 ** 3)
    return PreflightCheck("IPSW file", "ok", f"valido: {message} ({size_gb:.2f} GB)")


def _analyze_ipsw_for_preflight(ipsw_path: str):
    valid, message = validate_ipsw(ipsw_path)

    if not valid:
        return None, message

    analysis = analyze_ipsw(message)
    return analysis, message


def _check_ipsw_manifest_and_compatibility(
    ipsw_path: str,
    product_type: str | None,
) -> PreflightCheck:
    analysis, error = _analyze_ipsw_for_preflight(ipsw_path)

    if analysis is None:
        return PreflightCheck("IPSW compatibilità", "fail", f"impossibile analizzare: {error}")

    if analysis.errors:
        return PreflightCheck(
            "IPSW compatibilità",
            "fail",
            "; ".join(analysis.errors),
        )

    if not analysis.build_manifest_found:
        return PreflightCheck(
            "IPSW compatibilità",
            "fail",
            "BuildManifest.plist non trovato",
        )

    version = analysis.product_version or "versione sconosciuta"
    build = analysis.product_build_version or "build sconosciuta"

    if not product_type or product_type == "-":
        return PreflightCheck(
            "IPSW compatibilità",
            "warn",
            f"manifest valido ({version}, {build}), ma ProductType device non rilevato",
        )

    compatibility = analysis.supports_product_type(product_type)

    if compatibility is True:
        return PreflightCheck(
            "IPSW compatibilità",
            "ok",
            f"{product_type} supportato da IPSW {version} ({build})",
        )

    if compatibility is False:
        return PreflightCheck(
            "IPSW compatibilità",
            "fail",
            f"{product_type} NON è presente nei ProductType supportati dall'IPSW",
        )

    return PreflightCheck(
        "IPSW compatibilità",
        "warn",
        f"manifest valido ({version}, {build}), ma lista ProductType non determinabile",
    )


def _check_ipsw_signing(
    ipsw_path: str,
    product_type: str | None,
) -> PreflightCheck:
    analysis, error = _analyze_ipsw_for_preflight(ipsw_path)

    if analysis is None:
        return PreflightCheck("IPSW signing", "fail", f"impossibile verificare: {error}")

    if analysis.errors:
        return PreflightCheck("IPSW signing", "fail", "; ".join(analysis.errors))

    if not product_type or product_type == "-":
        return PreflightCheck(
            "IPSW signing",
            "warn",
            "ProductType non rilevato; impossibile verificare signing per-device",
        )

    status = check_ipsw_me_signing_status(
        product_type=product_type,
        version=analysis.product_version,
        build=analysis.product_build_version,
    )

    if status.ok:
        return PreflightCheck(
            "IPSW signing",
            "ok",
            status.summary(),
        )

    if status.unsigned:
        return PreflightCheck(
            "IPSW signing",
            "fail",
            status.summary(),
        )

    return PreflightCheck(
        "IPSW signing",
        "warn",
        status.summary(),
    )


def _check_product_type(product_type: str | None) -> PreflightCheck:
    if product_type and product_type != "-":
        return PreflightCheck("ProductType", "ok", product_type)

    return PreflightCheck(
        "ProductType",
        "warn",
        "non rilevato; premi Rileva stato o Info device prima di procedere",
    )


def _check_connection_state(connection_state: str) -> PreflightCheck:
    normalized = connection_state.lower().strip()

    if "recovery" in normalized:
        return PreflightCheck("Stato device", "ok", connection_state)

    if "dfu" in normalized:
        return PreflightCheck("Stato device", "ok", connection_state)

    if "normal" in normalized:
        return PreflightCheck(
            "Stato device",
            "warn",
            "Normal Mode; consigliato entrare in Recovery prima del restore",
        )

    return PreflightCheck(
        "Stato device",
        "warn",
        "stato non confermato; premi Rileva stato prima del restore",
    )


def run_preflight_checks(
    ipsw_path: str,
    product_type: str | None,
    connection_state: str,
) -> list[PreflightCheck]:
    checks: list[PreflightCheck] = []

    checks.append(_check_command("idevice_id", required=True))
    checks.append(_check_command("ideviceinfo", required=True))
    checks.append(_check_command("ideviceenterrecovery", required=True))
    checks.append(_check_command("idevicerestore", required=True))

    checks.append(_check_command("irecovery", required=False))
    checks.append(_check_command("idevicesyslog", required=False))

    checks.append(_check_ipsw_file(ipsw_path))
    checks.append(_check_ipsw_manifest_and_compatibility(ipsw_path, product_type))
    checks.append(_check_ipsw_signing(ipsw_path, product_type))
    checks.append(_check_product_type(product_type))
    checks.append(_check_connection_state(connection_state))
    checks.append(_check_log_dir())

    return checks


def summarize_preflight(checks: list[PreflightCheck]) -> tuple[str, str]:
    failures = [check for check in checks if check.fail]
    warnings = [check for check in checks if check.warn]

    if failures:
        headline = f"NOT READY - {len(failures)} errore/i, {len(warnings)} warning"
    elif warnings:
        headline = f"READY WITH WARNINGS - {len(warnings)} warning"
    else:
        headline = "READY - tutti i controlli principali sono OK"

    details = "\n".join(check.to_line() for check in checks)
    return headline, details
