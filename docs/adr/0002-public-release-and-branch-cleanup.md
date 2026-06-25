# 2. Public release & native branch cleanup

Date: 2026-06-25

## Status

Accepted

## Context

The tool started as a personal workbench helper. The genuinely distinctive part — mapping
Git/GitHub status onto Finder folder icons and tags — is broadly useful and macOS-specific,
so it is worth releasing as a small open-source tool. A public release must not leak the
author's internal project inventory or environment.

Separately, "stay clean" should also cover stale Git **branches**, the idea behind the
`git-sweep` tool.

## Decision

- **Release publicly** under a personal account, MIT-licensed, with the Finder-status mapping
  as the headline feature and the cleanup report as a bonus.
- **Keep user-specific data out of the repo.** `reports/`, `state.json`, `.icon_state.json`,
  `symbols.json`, the real `*.plist` and `tasks/` are git-ignored. Shipped instead:
  `symbols.example.json` and `launchd.plist.template`. No org names or absolute paths in code;
  the owner→short-name mapping is config-driven (`owner_aliases`).
- **Branch cleanup is reimplemented natively, not via `git-sweep`.** The upstream `git-sweep`
  is Python-2-era and unmaintained; depending on it is a supply-chain risk. Instead the
  janitor lists, per repo, local branches merged into the default branch plus branches whose
  upstream is `[gone]`, and suggests `git branch -d`. **Recommend-only**, consistent with the
  rest; no automatic `git fetch` (no network side effects), so results reflect local state.

## Consequences

- A fresh clone runs with sensible defaults; users add their own `symbols.json`.
- Branch suggestions can be slightly stale until the user fetches — acceptable for a hint.
- The repo carries only generic, secret-free content (verified with a secret scan before push).
