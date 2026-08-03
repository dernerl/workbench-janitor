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

## Setup

Requirements: macOS, `python3`, `git`, [`gh`](https://cli.github.com/) (logged in, for repo
visibility).

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

### Scheduling

Run it on an interval from any session that already has access to your projects folder
(e.g. a shell loop, or your editor/agent). For an unattended `launchd` job see
`launchd.plist.template` — note that protected folders (`~/Desktop`, `~/Documents`,
`~/Downloads`) require **Full Disk Access** for background agents.

See `docs/adr/` for the design decisions.

## Caveats

macOS-only. The cleanup suggestions are based on local state (no automatic `git fetch`).
