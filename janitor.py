#!/usr/bin/env python3
"""workbench-janitor — local cleanup helper for a directory full of project folders.

Scannt alle Projektordner, klassifiziert sie (in GitHub gesichert / ungesichert /
nur lokal / aktiv), korrigiert die `gh *`-Finder-Tags passend zum echten GitHub-Status
und schreibt einen Report + state.json + eine macOS-Notification.

Empfiehlt nur — löscht nie selbst.
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

# ── Config (per ENV überschreibbar) ────────────────────────────────────────────
WORKBENCH = Path(os.environ.get("JANITOR_WORKBENCH", Path(__file__).resolve().parent.parent))
STALE_DAYS = int(os.environ.get("JANITOR_STALE_DAYS", "30"))        # gesichert+ruhig → löschbar
LOCAL_STALE_DAYS = int(os.environ.get("JANITOR_LOCAL_STALE_DAYS", "30"))  # nur-lokal+ruhig → fragen
SELF_DIR = Path(__file__).resolve().parent
REPORTS = SELF_DIR / "reports"

# Ordner die nie betrachtet werden (der Janitor selbst, Claude-State, versteckte)
EXCLUDE = {SELF_DIR.name, ".claude", ".git"}
# Beim Ermitteln des "newest file" übersprungen (kein echter Arbeitsfortschritt)
SKIP_WALK = {".git", "node_modules", ".venv", "venv", ".build", "DerivedData",
             ".next", "dist", "build", "__pycache__", ".mypy_cache"}

TAG_PREFIX = "gh "  # nur diese Tags verwaltet der Janitor; andere (z.B. "Design") bleiben

# Finder-Farbindizes (wie im github-publish-Skill)
COLOR = {"none": 0, "gray": 1, "green": 2, "purple": 3,
         "blue": 4, "yellow": 5, "red": 6, "orange": 7}

SYMBOLS_FILE = SELF_DIR / "symbols.json"


def tag_color_index(expected_tag: str) -> int:
    # Schema aus der Finder-Sidebar: NOT→rot, public→orange, private→grün
    if expected_tag == "gh NOT":
        return COLOR["red"]
    if expected_tag.endswith("public"):
        return COLOR["orange"]
    if expected_tag.endswith("private"):
        return COLOR["green"]
    return COLOR["none"]


# owner-Aliase (GitHub-Login → Kurzname im Tag-Schema), aus symbols.json befüllt
OWNER_ALIASES: dict[str, str] = {}


def owner_short(owner: str) -> str:
    """GitHub-Owner → Kurzname. Aliase aus symbols.json (Substring-Match), sonst Login selbst."""
    o = owner.lower()
    for key, short in OWNER_ALIASES.items():
        if key.lower() in o:
            return short
    return o


# ── Datenmodell ─────────────────────────────────────────────────────────────--
@dataclass
class Project:
    name: str
    has_git: bool = False
    remote: str | None = None
    host: str | None = None
    owner: str | None = None
    repo: str | None = None
    dirty: bool = False
    unpushed: int = 0
    visibility: str | None = None        # "public" | "private" | None
    remote_missing: bool = False         # Remote zeigt auf nicht-existentes GitHub-Repo
    branches_prunable: list[str] = field(default_factory=list)  # gemergt/verwaist
    age_days: int = 0
    category: str = ""
    recommendation: str = ""
    current_tags: list[str] = field(default_factory=list)
    expected_tag: str | None = None
    tag_changed: bool = False
    note: str = ""


# ── Helpers ────────────────────────────────────────────────────────────────--
def run(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "").strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 1, ""


def newest_age_days(d: Path) -> int:
    newest = 0.0
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in SKIP_WALK]
        for f in files:
            if f == ".DS_Store" or f.startswith("._"):
                continue
            try:
                m = os.path.getmtime(os.path.join(root, f))
                if m > newest:
                    newest = m
            except OSError:
                pass
    if newest == 0.0:
        try:
            newest = os.path.getmtime(d)
        except OSError:
            newest = time.time()
    return int((time.time() - newest) // 86400)


def parse_owner_repo(remote: str) -> tuple[str | None, str | None, str | None]:
    """github.com Owner/Repo aus einer git-Remote-URL ziehen."""
    r = remote.rstrip("/")
    if r.endswith(".git"):
        r = r[:-4]
    host = owner = repo = None
    if "github.com" in r:
        host = "github.com"
        tail = r.split("github.com", 1)[1].lstrip(":/")
        parts = tail.split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
    return host, owner, repo


# ── Finder-Tags via xattr-bplist (kein Brew nötig) ─────────────────────────────
TAG_XATTR = "com.apple.metadata:_kMDItemUserTags"


def read_tags_raw(d: Path) -> list[str]:
    # Roh-Einträge inkl. Farb-Suffix ("Name" oder "Name\n<colorindex>")
    rc, hexout = run(["xattr", "-px", TAG_XATTR, str(d)])
    if rc != 0 or not hexout:
        return []
    try:
        raw = bytes.fromhex("".join(hexout.split()))
        return [str(i) for i in plistlib.loads(raw)]
    except Exception:
        return []


def tag_name(entry: str) -> str:
    return entry.split("\n", 1)[0]


def read_tags(d: Path) -> list[str]:
    return [tag_name(e) for e in read_tags_raw(d)]


def write_tags_raw(d: Path, entries: list[str]) -> None:
    data = plistlib.dumps(list(entries), fmt=plistlib.FMT_BINARY)
    rc, _ = run(["xattr", "-wx", TAG_XATTR, data.hex(), str(d)])
    if rc != 0:
        raise OSError(f"xattr write failed for {d}")


# ── Kern ───────────────────────────────────────────────────────────────────--
def collect(d: Path) -> Project:
    p = Project(name=d.name)
    p.age_days = newest_age_days(d)
    p.current_tags = read_tags(d)

    if (d / ".git").exists():
        p.has_git = True
        rc, remote = run(["git", "remote", "get-url", "origin"], cwd=d)
        if rc == 0 and remote:
            p.remote = remote
            p.host, p.owner, p.repo = parse_owner_repo(remote)
        rc, st = run(["git", "status", "--porcelain"], cwd=d)
        p.dirty = bool(st.splitlines())
        rc, ahead = run(["git", "rev-list", "--count", "@{u}..HEAD"], cwd=d)
        p.unpushed = int(ahead) if rc == 0 and ahead.isdigit() else 0

    return p


def default_branch(d: Path) -> str | None:
    rc, head = run(["git", "symbolic-ref", "--quiet", "--short",
                    "refs/remotes/origin/HEAD"], cwd=d)
    if rc == 0 and "/" in head:
        return head.split("/", 1)[1]
    for cand in ("main", "master"):
        rc, _ = run(["git", "show-ref", "--verify", "--quiet",
                     f"refs/heads/{cand}"], cwd=d)
        if rc == 0:
            return cand
    return None


def lookup_branches(p: Project, d: Path) -> None:
    """git-sweep-Konzept nativ: lokale Branches, die in den Default gemergt oder verwaist sind."""
    if not p.has_git:
        return
    base = default_branch(d)
    if not base:
        return
    rc, cur = run(["git", "symbolic-ref", "--quiet", "--short", "HEAD"], cwd=d)
    keep = {base, cur.strip()}
    prunable: set[str] = set()
    rc, merged = run(["git", "branch", "--merged", base,
                      "--format=%(refname:short)"], cwd=d)
    if rc == 0:
        prunable |= {b for b in merged.splitlines() if b and b not in keep}
    # Branches, deren Upstream auf dem Remote weg ist ([gone])
    rc, tracks = run(["git", "for-each-ref",
                      "--format=%(refname:short) %(upstream:track)", "refs/heads"], cwd=d)
    if rc == 0:
        prunable |= {l.split(" ", 1)[0] for l in tracks.splitlines()
                     if "[gone]" in l and l.split(" ", 1)[0] not in keep}
    p.branches_prunable = sorted(prunable)


def lookup_visibility(p: Project) -> None:
    if not (p.host == "github.com" and p.owner and p.repo):
        return
    try:
        r = subprocess.run(
            ["gh", "repo", "view", f"{p.owner}/{p.repo}", "--json", "visibility",
             "-q", ".visibility"],
            capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return
    if r.returncode == 0 and r.stdout.strip():
        p.visibility = r.stdout.strip().lower()
    elif "Could not resolve to a Repository" in (r.stderr or ""):
        p.remote_missing = True


def classify(p: Project) -> None:
    if not p.has_git:
        if p.age_days > LOCAL_STALE_DAYS:
            p.category = "local-stale"
            p.recommendation = (f"Nur lokal, seit {p.age_days} Tagen unangetastet — "
                                "löschen oder nach GitHub sichern?")
        else:
            p.category = "local-active"
        return

    if not p.remote:
        p.category = "no-remote"
        extra = " (uncommittete Änderungen)" if p.dirty else ""
        p.recommendation = f"Git-Repo ohne Remote{extra} — auf GitHub pushen oder Absicht?"
        return

    if p.remote_missing:
        p.category = "remote-gone"
        dirty_warn = " — ⚠️ enthält uncommittete Änderungen!" if p.dirty else ""
        p.recommendation = (f"Remote `{p.owner}/{p.repo}` existiert nicht (mehr) auf GitHub — "
                            f"neu pushen oder Remote/Ordner bereinigen{dirty_warn}")
        return

    if p.dirty or p.unpushed > 0:
        p.category = "dirty"
        bits = []
        if p.dirty:
            bits.append("uncommittete Änderungen")
        if p.unpushed > 0:
            bits.append(f"{p.unpushed} ungepushte Commit(s)")
        p.recommendation = f"{' + '.join(bits)} — committen & pushen, bevor lokal aufgeräumt wird"
        return

    # clean + gepusht
    if p.age_days > STALE_DAYS:
        p.category = "synced-stale"
        p.recommendation = (f"In GitHub gesichert & seit {p.age_days} Tagen ruhig — "
                            "lokal löschbar")
    else:
        p.category = "synced-active"


def derive_expected_tag(p: Project) -> None:
    if not p.has_git or not p.remote:
        p.expected_tag = "gh NOT"
        return
    if p.host != "github.com" or not p.owner:
        p.expected_tag = "gh NOT"
        return
    if not p.visibility:
        if not p.remote_missing:  # remote-gone wird schon als Kategorie erklärt
            p.note = "Sichtbarkeit via gh nicht ermittelbar (kein Zugriff?) — Tag nicht geändert"
        p.expected_tag = None
        return
    p.expected_tag = f"gh {owner_short(p.owner)} {p.visibility}"


def load_symbols() -> dict:
    try:
        return json.loads(SYMBOLS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"owner_aliases": {}}


def reconcile_tag(p: Project, d: Path, apply: bool) -> None:
    if p.expected_tag is None:
        return
    expected_entry = f"{p.expected_tag}\n{tag_color_index(p.expected_tag)}"
    raw = read_tags_raw(d)
    managed_now = [e for e in raw if tag_name(e).startswith(TAG_PREFIX)]
    if managed_now == [expected_entry]:
        return  # Name UND Farbe stimmen
    keep = [e for e in raw if not tag_name(e).startswith(TAG_PREFIX)]  # z.B. "Design" bleibt
    p.tag_changed = True
    if apply:
        write_tags_raw(d, keep + [expected_entry])


# ── Output ─────────────────────────────────────────────────────────────────--
GROUPS = [
    ("remote-gone",  "🔴 Remote fehlt auf GitHub — prüfen!"),
    ("synced-stale", "🟢 In GitHub gesichert — lokal löschbar"),
    ("dirty",        "🟡 Ungesicherte Änderungen — erst committen/pushen"),
    ("no-remote",    "🟠 Git ohne Remote — auf GitHub?"),
    ("local-stale",  "🔵 Nur lokal & alt — löschen oder sichern?"),
]


def build_report(projects: list[Project], applied: bool) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = [f"# 🧹 Workbench Janitor — {now}", "",
           f"Workbench: `{WORKBENCH}` · {len(projects)} Ordner · "
           f"Schwellen: gesichert>{STALE_DAYS}d, lokal>{LOCAL_STALE_DAYS}d", ""]

    by_cat: dict[str, list[Project]] = {}
    for p in projects:
        by_cat.setdefault(p.category, []).append(p)

    for cat, title in GROUPS:
        items = sorted(by_cat.get(cat, []), key=lambda x: -x.age_days)
        if not items:
            continue
        out.append(f"## {title}  ({len(items)})")
        out.append("")
        for p in items:
            out.append(f"- **{p.name}** — {p.recommendation}")
            if p.note:
                out.append(f"  - ⚠️ {p.note}")
        out.append("")

    # Tag-Änderungen
    changed = [p for p in projects if p.tag_changed]
    verb = "korrigiert" if applied else "WÜRDE korrigieren (dry-run)"
    out.append(f"## 🏷️ Finder-Tags {verb}  ({len(changed)})")
    out.append("")
    if changed:
        for p in changed:
            now_tags = ", ".join(t for t in p.current_tags if t.startswith(TAG_PREFIX)) or "—"
            out.append(f"- **{p.name}**: `{now_tags}` → `{p.expected_tag}`")
    else:
        out.append("- alle Tags stimmen ✓")
    out.append("")

    # Branch-Cleanup (git-sweep-Konzept)
    with_branches = sorted([p for p in projects if p.branches_prunable],
                           key=lambda x: -len(x.branches_prunable))
    if with_branches:
        total = sum(len(p.branches_prunable) for p in with_branches)
        out.append(f"## 🌿 Branches löschbar — gemergt/verwaist  ({total} in "
                   f"{len(with_branches)} Repos)")
        out.append("")
        for p in with_branches:
            out.append(f"- **{p.name}**: `{'`, `'.join(p.branches_prunable)}`  "
                       f"→ `git -C {p.name} branch -d {p.branches_prunable[0]}`")
        out.append("")

    # Ruhe-Liste
    active = sorted(
        [p for p in projects if p.category in ("synced-active", "local-active")],
        key=lambda x: x.age_days)
    out.append(f"## ✅ Aktiv / in Ruhe lassen  ({len(active)})")
    out.append("")
    for p in active:
        out.append(f"- {p.name} (vor {p.age_days}d angefasst)")
    out.append("")
    return "\n".join(out)


def summary_counts(projects: list[Project]) -> dict[str, int]:
    c = {"remote-gone": 0, "synced-stale": 0, "dirty": 0, "no-remote": 0,
         "local-stale": 0, "tags": 0}
    for p in projects:
        if p.category in c:
            c[p.category] += 1
        if p.tag_changed:
            c["tags"] += 1
    return c


def notify(counts: dict[str, int]) -> None:
    gone = f"🔴{counts['remote-gone']} remote-weg · " if counts['remote-gone'] else ""
    msg = (f"{gone}🟢{counts['synced-stale']} löschbar · 🟡{counts['dirty']} dirty · "
           f"🔵{counts['local-stale']} alt-lokal · 🏷️{counts['tags']} Tags")
    script = (f'display notification "{msg}" with title "🧹 Workbench Janitor" '
              f'subtitle "Report aktualisiert"')
    run(["osascript", "-e", script])


def main() -> int:
    ap = argparse.ArgumentParser(description="Workbench Janitor")
    ap.add_argument("--dry-run", action="store_true",
                    help="Tags nicht schreiben, nur zeigen was passieren würde")
    ap.add_argument("--no-notify", action="store_true", help="keine macOS-Notification")
    args = ap.parse_args()
    apply = not args.dry_run

    if not WORKBENCH.is_dir():
        print(f"Workbench nicht gefunden: {WORKBENCH}", file=sys.stderr)
        return 1

    dirs = sorted(
        d for d in WORKBENCH.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in EXCLUDE
    )

    symbols = load_symbols()
    OWNER_ALIASES.update(symbols.get("owner_aliases", {}))

    projects: list[Project] = []
    for d in dirs:
        p = collect(d)
        lookup_visibility(p)
        lookup_branches(p, d)
        classify(p)
        derive_expected_tag(p)
        reconcile_tag(p, d, apply)
        projects.append(p)

    REPORTS.mkdir(parents=True, exist_ok=True)
    report = build_report(projects, applied=apply)
    stamp = datetime.now().strftime("%Y-%m-%d")
    (REPORTS / f"{stamp}.md").write_text(report, encoding="utf-8")
    (REPORTS / "latest.md").write_text(report, encoding="utf-8")

    state = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "workbench": str(WORKBENCH),
        "applied": apply,
        "summary": summary_counts(projects),
        "projects": [asdict(p) for p in projects],
    }
    (SELF_DIR / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = summary_counts(projects)
    if not args.no_notify:
        notify(counts)

    print(report)
    print(f"\n→ Report: {REPORTS/'latest.md'}  ·  state.json geschrieben"
          f"  ·  Tags {'angewendet' if apply else 'NICHT angewendet (dry-run)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
