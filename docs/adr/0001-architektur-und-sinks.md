# 1. Architecture & sinks

Date: 2026-06-25

## Status

Accepted, but two of the decisions below have since been replaced:

- "Folder icons = ownership, colour = status" is superseded by
  [ADR 0003](0003-tags-only-drop-folder-icons.md) — the Finder tag is now the only visual
  signal; no custom icons are written.
- "Scheduling stays in an already-authorised session" is superseded by
  [ADR 0004](0004-swiftbar-menubar-surface.md) — SwiftBar's refresh timer is the scheduler.

The rest (recommend-only, deterministic Python core, local auth-free sinks, tags via xattr)
still stands.

## Context

Many project folders sit side by side in one directory. Some are backed up on GitHub and
finished (safe to delete locally), some are local-only and long untouched (delete?), some
have uncommitted changes. The goal is to see each folder's status directly in Finder and get
regular, low-friction cleanup suggestions.

## Decision

- **Recommend-only.** The janitor never deletes. It classifies and suggests. Deletion is
  destructive; the decision stays with the user.
- **Deterministic core in Python, no LLM.** `janitor.py` does scan, classification, tag/icon
  reconcile and output. `janitor.sh` is a thin launchd wrapper (PATH setup). Reproducible,
  fast, free, testable.
- **Local, auth-free sinks.** Output is `report.md` (readable) + `state.json`
  (machine-readable) + a macOS notification (visibility). No cloud account required.
- **Finder tags without a Homebrew dependency.** Written directly via the
  `com.apple.metadata:_kMDItemUserTags` xattr (binary plist). Only `gh *` tags are managed;
  manual tags are preserved.
- **Folder icons = ownership, colour = status.** A tinted SF Symbol is set as the folder icon
  (`NSWorkspace.setIcon`): shape encodes the owner, colour encodes Git/GitHub status. Change
  tracked in `.icon_state.json` so icons are only re-rendered when something changes.
- **Scheduling stays in an already-authorised session, not launchd.** Protected folders
  (`~/Desktop`, `~/Documents`, `~/Downloads`) are TCC-guarded; a launchd agent fails to read
  them without Full Disk Access. Running from a session that already has access avoids that.
  launchd remains a documented option (template, requires FDA).

## Consequences

- Runs immediately: no cloud auth, no Homebrew dependency.
- Unattended automation in protected folders needs Full Disk Access (trade-off vs. TCC).
- Finder reflects Git/GitHub status at a glance; wrong/missing tags and icons get corrected.
- A `remote-gone` category also surfaces repos whose GitHub remote has disappeared.
