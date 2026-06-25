# 🧹 workbench-janitor

**See at a glance — in Finder itself — where each of your projects lives and who owns it.**

If you keep many project folders side by side (some pushed to GitHub, some local-only,
some half-finished), `workbench-janitor` turns that pile into something readable: it maps
each folder's real Git/GitHub status onto its **Finder folder icon and tag**, and reports
what you can safely clean up. macOS-only. Recommend-only — it never deletes anything.

<img width="284" height="262" alt="image" src="https://github.com/user-attachments/assets/81065f10-a721-40e6-9d8d-eaf9374be344" />

## The Finder mapping

| | meaning |
|---|---|
| 🏠 **house icon** | owned by your personal account |
| 🏢 **building icon** | owned by an organisation/company |
| 📁 **plain folder** | local only, no GitHub remote |
| 🟢 **green** | private repo |
| 🟠 **orange** | public repo |
| 🔴 **red** | local only / remote gone |

Icon shape answers *who owns it*, colour answers *where it lives*. One glance, done.
The same status is mirrored as a Finder **tag** (`gh <owner> <visibility>`) so you can also
filter by it. Your manual tags are left untouched.

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

## Setup

Requirements: macOS, `python3`, `git`, [`gh`](https://cli.github.com/) (logged in, for repo
visibility), Xcode command line tools (`swift`, for the folder icons).

```bash
git clone <this repo>
cd workbench-janitor
cp symbols.example.json symbols.json    # set your owner→icon mapping
JANITOR_WORKBENCH=/path/to/your/projects python3 janitor.py
```

By default the workbench is the **parent** of this folder, so dropping `workbench-janitor`
into your projects directory just works.

### Options

```bash
python3 janitor.py            # tags + icons + report + notification
python3 janitor.py --dry-run  # change nothing, just show what would happen
python3 janitor.py --no-icons # skip folder icons (faster)
python3 janitor.py --no-notify
```

### Config — `symbols.json`

```json
{
  "owner_aliases": { "my-github-org": "work", "my-login": "me" },
  "by_owner":      { "me": "house.fill", "work": "building.2.fill" },
  "default":       "folder.fill"
}
```

`owner_aliases` maps GitHub owners to short names (substring match); `by_owner` maps those to
[SF Symbol](https://developer.apple.com/sf-symbols/) names used as the folder icon.

### Scheduling

Run it on an interval from any session that already has access to your projects folder
(e.g. a shell loop, or your editor/agent). For an unattended `launchd` job see
`launchd.plist.template` — note that protected folders (`~/Desktop`, `~/Documents`,
`~/Downloads`) require **Full Disk Access** for background agents.

## How it stays clean

- Custom folder icons create an `Icon\r` file; it's added to each repo's
  `.git/info/exclude` and filtered from both the dirty- and the staleness check, so it never
  shows up as a change or resets a project's "last touched" time.
- Icons are only re-rendered when the owner/status actually changes (`.icon_state.json`).
- A targeted Finder refresh runs after each icon change (no `killall Finder`).

See `docs/adr/` for the design decisions.

## Caveats

macOS-only. `NSWorkspace.setIcon` + Finder icon caching can be finicky; a manual
`killall Finder` forces a full refresh. The cleanup suggestions are based on local state
(no automatic `git fetch`).
