"""Optionaler Zusatzschritt zu janitor.py: Ein-Satz-Ordnerbeschreibungen.

Additiv zu ADR 0001 (deterministischer Kern, kein LLM) — siehe ADR 0005. Läuft isoliert,
schreibt eine eigene `descriptions.json` (state.json bleibt unverändert) und degradiert
restlos, wenn kein Backend verfügbar ist.

Backends (siehe ADR 0005 für den Bake-off dahinter):
  1. Apple Intelligence (nativ, `tools/describe_apple.swift`) — Primär, kostenlos, on-device.
  2. Pi + Azure Foundry (`pi -p ... --model foundry-chat/o4-mini`) — Fallback, falls Apple
     Intelligence auf einem Gerät nicht verfügbar ist.
Kein `claude -p`: dieses Tool läuft unbeaufsichtigt per SwiftBar-Timer, ein automatisierter
Claude-Code-Aufruf darin würde Nutzungskontingent ohne aktive Anfrage verbrauchen.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

SELF_DIR = Path(__file__).resolve().parent
CACHE_FILE = SELF_DIR / "descriptions.json"
DESCRIBE_APPLE_SWIFT = SELF_DIR / "tools" / "describe_apple.swift"

PROMPT = ("Beschreibe in einem Satz (max. 20 Wörter, Deutsch), wofür dieser "
          "Ordner/dieses Projekt ist. Antworte nur mit dem Satz, ohne Einleitung.")

IGNORE_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", ".DS_Store"}

CALL_TIMEOUT = 60  # Sekunden pro Backend-Aufruf


def gather_context(folder: Path) -> str:
    """Signal für die Beschreibung sammeln — portiert aus dem Bake-off-Spike."""
    parts: list[str] = []

    readme = next((f for f in folder.glob("README*") if f.is_file()), None)
    if readme:
        try:
            text = readme.read_text(errors="ignore")
            parts.append("README (Auszug):\n" + "\n".join(text.splitlines()[:40]))
        except Exception:
            pass

    for manifest, key in [("package.json", '"description"'), ("pyproject.toml", "description")]:
        mf = folder / manifest
        if mf.is_file():
            try:
                text = mf.read_text(errors="ignore")
                for line in text.splitlines():
                    if key in line:
                        parts.append(f"{manifest}: {line.strip()}")
                        break
            except Exception:
                pass

    if (folder / ".git").is_dir():
        try:
            subject = subprocess.run(
                ["git", "-C", str(folder), "log", "-1", "--format=%s"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            if subject:
                parts.append(f"Letzter Commit: {subject}")
        except Exception:
            pass
        try:
            remote = subprocess.run(
                ["git", "-C", str(folder), "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            if remote:
                parts.append(f"Remote: {remote}")
        except Exception:
            pass

    if not parts:
        entries = [p.name for p in sorted(folder.iterdir()) if p.name not in IGNORE_DIRS][:25]
        parts.append("Ordnerinhalt: " + ", ".join(entries))

    return "\n\n".join(parts)[:1500]


def signal_hash(signal: str) -> str:
    return "sha256:" + hashlib.sha256(signal.encode("utf-8")).hexdigest()


def _describe_apple(context: str) -> str | None:
    if not DESCRIBE_APPLE_SWIFT.is_file() or not shutil.which("swift"):
        return None
    try:
        result = subprocess.run(
            ["swift", str(DESCRIBE_APPLE_SWIFT), context],
            capture_output=True, text=True, timeout=CALL_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _describe_pi_foundry(context: str) -> str | None:
    if not shutil.which("pi"):
        return None
    try:
        result = subprocess.run(
            ["pi", "-p", "--no-tools", "--no-session", "--model", "foundry-chat/o4-mini",
             f"{PROMPT}\n\n{context}"],
            capture_output=True, text=True, timeout=CALL_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def backends_available() -> bool:
    apple_ok = DESCRIBE_APPLE_SWIFT.is_file() and bool(shutil.which("swift"))
    pi_ok = bool(shutil.which("pi"))
    return apple_ok or pi_ok


def generate_description(context: str) -> tuple[str, str] | tuple[None, None]:
    """Backend-Kaskade: Apple Intelligence zuerst, Pi+Foundry als Fallback."""
    desc = _describe_apple(context)
    if desc:
        return desc, "apple"
    desc = _describe_pi_foundry(context)
    if desc:
        return desc, "pi-foundry"
    return None, None


def load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def update_descriptions(dirs: list[Path], budget: int) -> dict:
    """Cache-Misses (neu/geändert) bis `budget` Stück auffrischen, Rest unverändert lassen."""
    cache = load_cache()
    if not backends_available():
        return cache  # weder Apple Intelligence noch pi verfügbar — Cache unangetastet lassen
    spent = 0

    for d in dirs:
        if spent >= budget:
            break
        context = gather_context(d)
        h = signal_hash(context)
        entry = cache.get(str(d))
        if entry and entry.get("signal_hash") == h:
            continue  # Cache-Hit, kein Aufruf nötig

        desc, backend = generate_description(context)
        spent += 1
        if desc is None:
            continue  # kein Backend verfügbar/erfolgreich — alten Eintrag (falls vorhanden) behalten
        cache[str(d)] = {
            "description": desc,
            "backend": backend,
            "signal_hash": h,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    save_cache(cache)
    return cache
