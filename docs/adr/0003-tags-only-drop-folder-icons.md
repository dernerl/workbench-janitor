# 3. Tags only — drop folder icons

Date: 2026-07-29

## Status

Accepted. Supersedes the icon part of [ADR 0002](0002-public-release-and-branch-cleanup.md).

## Context

The janitor mirrored each folder's Git/GitHub status twice: as a Finder **tag**
(`gh <owner> <visibility>`) and as a **custom folder icon** (SF Symbol shape = owner,
tint = visibility, via `NSWorkspace.setIcon` in `lib/set_folder_icon.swift`).

The icon path carried disproportionate cost for the extra signal (owner as *shape* instead of
just being present in the tag string):

- Depended on Xcode command line tools (`swift`) purely to render a folder thumbnail.
- `NSWorkspace.setIcon` + Finder's icon cache was finicky — needed a targeted
  `osascript … tell Finder to update` after every change, and still needed manual
  `killall Finder` sometimes.
- Left an `Icon\r` resource file in every managed folder, which in turn had to be filtered out
  of the dirty-check and the staleness (`newest_age_days`) walk, and added to each repo's
  `.git/info/exclude` — three separate pieces of bookkeeping to keep one rendering artifact
  invisible to Git and to the tool's own logic.
- Needed its own cache (`.icon_state.json`) just to avoid needless re-renders.

None of that made the underlying information more actionable — the same owner/visibility
status was already sitting in the tag, filterable and groupable in Finder's sidebar without
any of the above.

## Decision

- **Drop custom folder icons entirely.** The Finder tag (`gh <owner> <visibility>`, colour
  red/orange/green) is now the only visual signal the janitor manages.
- Removed: `lib/set_folder_icon.swift`, `.icon_state.json`, `reconcile_icon()`,
  `ensure_git_ignores_icon()`, the `Icon\r` filtering in `collect()`/`newest_age_days()`, the
  `--no-icons` flag, and the `by_owner`/`default` icon-symbol keys in `symbols.json`.
- One-time cleanup: reset the custom icon (`NSWorkspace.setIcon(nil, …)`) on every folder that
  had one, and reverted the `Icon?` line the janitor had added to affected repos'
  `.git/info/exclude`.
- `symbols.json`'s `owner_aliases` stays — it still shortens the owner name in the tag string.

## Consequences

- One code path to maintain instead of two; no Xcode CLT dependency, no Finder-cache
  workarounds, no per-repo `Icon\r` bookkeeping.
- Owner is no longer distinguishable by shape at a glance in icon/grid view — only via the tag
  text/colour, which reads best in Finder's list/column view or via tag-based smart folders.
  Acceptable trade: this project's owner is checked in list/column view, not grid view.
- If shape-based scanning is ever needed again, the removed code is recoverable from Git
  history (this ADR's parent commit) rather than kept around unused.
