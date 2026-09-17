# 🧹 workbench-janitor

**See at a glance — in Finder itself — where each of your projects lives and who owns it.**

If you keep many project folders side by side (some pushed to GitHub, some local-only,
some half-finished), `workbench-janitor` turns that pile into something readable: it maps
each folder's real Git/GitHub status onto a Finder **tag**, and reports what you can safely
clean up. macOS-only. Recommend-only — it never deletes anything.

<img width="284" height="262" alt="image" src="https://github.com/user-attachments/assets/81065f10-a721-40e6-9d8d-eaf9374be344" />

## The Finder mapping

Each managed folder gets exactly one tag: `gh <owner> <visibility>` (e.g. `gh servo private`,
`gh dernerl public`, or `gh NOT` for local-only / no remote). The tag's Finder **colour**
answers *where it lives* at a glance:

| colour | meaning |
|---|---|
| 🟢 **green** | private repo |
| 🟠 **orange** | public repo |
| 🔴 **red** | local only / remote gone |

Filter or group by the tag in Finder's sidebar to see everything from one owner or
visibility at once. Your manual tags are left untouched.

## What it reports (recommend-only)

| Category | When | Suggestion |
|---|---|---|
| 🔴 remote-gone | remote no longer exists on GitHub | re-push / clean up |
| 🟢 synced-stale | pushed, clean, quiet > 30 days | safe to delete locally (it's backed up) |
| 🟡 dirty | uncommitted / unpushed changes | commit & push |
| 🟠 no-remote | git repo without a remote | push to GitHub? |
| 🔵 local-stale | no git, quiet > 30 days | delete or back up? |
| 🌿 branches | merged or `[gone]` local branches | prune (`git branch -d …`) |

Output: `reports/latest.md`, `state.json` (machine-readable), and a macOS notification with
the headline counts.

## Folder descriptions (optional)

Each folder can also get a cached, one-sentence description of what it's actually *for* —
generated from its README/manifest/last commit, not from Git metadata. This is a fully
optional, isolated add-on (see `docs/adr/0005-optional-llm-folder-descriptions.md`): the tool
works exactly the same without it.

- **Backend:** Apple Intelligence (native `FoundationModels`, via `tools/describe_apple.swift`)
  by default — free, on-device, no extra download. Falls back to `pi -p` against an Azure
  Foundry `o4-mini` deployment only if Apple Intelligence isn't available on the machine.
  `claude -p` is deliberately not used here — this tool runs unattended, and an automated
  Claude Code call in that loop would spend usage quota without you asking for it each time.
- **Cached, not recomputed every run:** stored in `descriptions.json` (gitignored, alongside
  `state.json` — separate file, so `state.json`'s schema stays untouched). A folder's
  description is only regenerated when its signal content (README, manifest, last commit)
  actually changes.
- **Budgeted:** at most `JANITOR_MAX_NEW_DESCRIPTIONS` (default `5`) new/changed descriptions
  per run, so importing many folders at once doesn't stall a SwiftBar refresh — the rest catch
  up over the following runs.
- **Disable it:** `python3 janitor.py --skip-descriptions`, or simply don't have `swift`
  (with Apple Intelligence enabled) or `pi` on `PATH` — the step is skipped silently either way.

## Dashboard (optional)

A static localhost page (`dashboard/index.html`) renders `state.json` + `descriptions.json` as
project cards — status, age, and description — instead of reading the Markdown report:

```bash
./dashboard.sh open    # starts a local server if needed, opens the dashboard in your browser
./dashboard.sh status
./dashboard.sh stop
```

Served via `python3 -m http.server` on `JANITOR_DASHBOARD_PORT` (default `8934`), bound to
`127.0.0.1`. No framework, no build step. Also reachable from the SwiftBar dropdown (see
below) via a "🖥️ Dashboard öffnen" entry.

## Setup

Requirements: macOS, `python3`, `git`, [`gh`](https://cli.github.com/) (logged in, for repo
visibility). Optional, for folder descriptions: Xcode CLT (`swift`) with Apple Intelligence
enabled, and/or [`pi`](https://github.com/earendil-works/pi) configured against an Azure
Foundry deployment as fallback.

```bash
git clone <this repo>
cd workbench-janitor
cp symbols.example.json symbols.json    # set your owner→short-name mapping
JANITOR_WORKBENCH=/path/to/your/projects python3 janitor.py
```

By default the workbench is the **parent** of this folder, so dropping `workbench-janitor`
into your projects directory just works.

### Options

```bash
python3 janitor.py            # tags + report + notification
python3 janitor.py --dry-run  # change nothing, just show what would happen
python3 janitor.py --no-notify
```

### Config — `symbols.json`

```json
{
  "owner_aliases": { "my-github-org": "work", "my-login": "me" }
}
```

`owner_aliases` maps GitHub owners to short names (substring match) used in the Finder tag.

### Scheduling & menu bar (recommended): SwiftBar

Every run writes a `state.json` next to `janitor.py` — that file is this tool's contract to
the outside world. The menu bar layer that reads it lives in a **separate** repo,
[dernerl/swiftbar-plugins](https://github.com/dernerl/swiftbar-plugins), so this tool stays
usable on its own:

```bash
brew install --cask swiftbar
git clone https://github.com/dernerl/swiftbar-plugins.git
cd swiftbar-plugins && ./install.sh   # first launch may ask for Desktop access — allow it
```

`install.sh` links the chosen plugin into `~/.swiftbar-plugins/` and points SwiftBar there
(never into a repo — SwiftBar executes *every* executable file in its plugin folder). The
plugin re-runs `janitor.py --no-notify` on its refresh interval and renders `state.json` as a
dropdown: one section per category, each folder a clickable link that opens it in Finder,
plus a link to `reports/latest.md`, a "🖥️ Dashboard öffnen" entry (starts/opens the localhost
dashboard above), and a manual refresh item. The badge count and colour tell you at a glance
whether anything needs attention — no more opening the report by hand. Add SwiftBar as a login
item so it survives reboots.

If this folder is not at `~/projects/workbench-janitor`, point the plugin at it with
`JANITOR_DIR` or the plugin repo's `config.sh`.

### Alternative: run it yourself

Run it on an interval from any session that already has access to your projects folder
(e.g. a shell loop, or your editor/agent). For an unattended `launchd` job see
`launchd.plist.template` — note that protected folders (`~/Desktop`, `~/Documents`,
`~/Downloads`) require **Full Disk Access** for background agents, which is why SwiftBar
(a normal foreground app) is the easier path.

See `docs/adr/` for the design decisions.

## Caveats

macOS-only. The cleanup suggestions are based on local state (no automatic `git fetch`).
