# 4. SwiftBar as the menu bar surface (and de facto scheduler)

Date: 2026-07-29

## Status

Accepted. The choice of SwiftBar stands; the *location* of the plugin was revised on
2026-08-03 when the presentation layer moved into its own repo — see
[`dernerl/swiftbar-plugins`, ADR 0001](https://github.com/dernerl/swiftbar-plugins/blob/main/docs/adr/0001-plugins-getrennt-von-tools.md).
The Decision section below already reflects that revision.

## Context

Two problems compounded. (1) Nothing ran the janitor regularly. ADR 0001 had already ruled
out `launchd` as the primary path — a background agent gets no TCC prompt and is silently
denied access to `~/Desktop`, so it fails without an error worth reading — and fell back to
"run it from a session that is already authorised". That fallback only runs while such a
session happens to be alive, which in practice meant the janitor ran when someone remembered
to start it. (2) Even when it did run, seeing the result meant opening `reports/latest.md` by
hand — no ambient signal that something needs a decision.

Two ways to get a persistent, glanceable surface were considered:

- **A custom native menu bar app** (SwiftUI + `NSStatusItem`): full control, could trigger
  actions (commit & push, open PR) directly from the dropdown — but needs its own Xcode
  project, code signing, and ongoing maintenance as a real app, for a tool whose core logic
  already lives in `janitor.py`.
- **SwiftBar**: an existing, actively maintained menu bar host that turns any script's stdout
  into a menu bar item + dropdown, on its own refresh timer. No Xcode, no signing, reuses
  `janitor.py` as-is.

## Decision

- **SwiftBar** (`brew install --cask swiftbar`) is the menu bar host.
- **The plugin does not live in this repo.** SwiftBar's plugin folder points at
  `~/.swiftbar-plugins/`, which holds only symlinks to the plugins actually wanted; the
  plugin sources live in the separate repo `dernerl/swiftbar-plugins`. Reasoning and the
  problems that forced the split are in that repo's ADR 0001 — in short: SwiftBar executes
  *every* executable file in its plugin folder, so pointing it into a working tree turns
  stray scripts into menu bar icons.
- **This repo's contract to the outside is `state.json`**, written next to `janitor.py`.
  Anything that wants to display janitor state reads that file; the janitor itself knows
  nothing about SwiftBar. The plugin locates this repo via `JANITOR_DIR` (env, then
  `config.sh`, then a default under `~/projects`).
- The plugin currently wired up is `combined.15m.sh`, which merges this tool and
  `azure-token-watchdog` into a single menu bar icon. Every 15 minutes it runs
  `janitor.py --no-notify` (tags get applied, same as a normal run) and renders `state.json`
  as its section of the dropdown — one entry per category, each folder a clickable `file://`
  link that opens it in Finder, plus a link to `reports/latest.md` and a manual
  "Jetzt aktualisieren" refresh item. The icon carries the combined open-item count of both
  tools and is tinted by the worse of the two states (red = remote-gone present,
  orange = dirty present).
- SwiftBar's own timer **is** the scheduler now — `--no-notify` is passed because the menu
  bar badge replaces the old `display notification` as the "something changed" signal.
- SwiftBar is a login item (`System Events → login item`) so it survives reboots without any
  manual step.

## Consequences

- Solves both original problems at once: the janitor now runs unattended on SwiftBar's
  refresh interval as long as SwiftBar is running, and its state is visible ambiently in the
  menu bar instead of requiring a manual look into `reports/latest.md`.
- Because SwiftBar is a normal foreground app (not a headless `launchd` agent), macOS can
  actually show the Desktop-access TCC prompt on first run — the exact permission that made
  the ADR 0001 `launchd` approach fail silently.
- No actions from the dropdown yet (open-only) — committing/pushing still happens in a
  terminal/editor. If that's ever wanted, `bash=` xbar params can call scripts, or the
  custom-app path from the rejected option could be revisited.
- Two more moving parts to know about when debugging: if the report looks stale, check that
  SwiftBar is running and that `~/.swiftbar-plugins/` still symlinks a working plugin, before
  suspecting `janitor.py` itself. Because the plugin resolves this repo by path, moving this
  folder breaks the menu bar without breaking the tool — the fix belongs in the plugin repo's
  `config.sh`, not here.
- The split cuts both ways: this repo no longer carries any SwiftBar code, so `janitor.py`
  stays runnable and testable on its own, but the surface a user actually sees is documented
  in a different repo. Hence the explicit pointer in the Status section above.
