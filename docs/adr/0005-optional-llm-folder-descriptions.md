# 5. Optional, cached folder descriptions via a local LLM backend

Date: 2026-09-17

## Status

Accepted. Additive to [ADR 0001](0001-architektur-und-sinks.md) — the core scan/classify/tag
pipeline stays deterministic and LLM-free; this ADR only covers a separate, optional step.

## Context

The janitor's classification (`dirty`, `synced-stale`, ...) is pure Git/GitHub metadata — it
says nothing about what a folder is *for*. With dozens of folders in the workbench, that
becomes hard to keep in your head. The ask: a short, cached, human-readable one-sentence
description per folder, generated once and only regenerated when the folder's signal content
(README, manifest, first commit) actually changes.

Generating that sentence needs an LLM, which conflicts with ADR 0001's "deterministic core, no
LLM, local/auth-free sinks" unless kept strictly additive: the description step must be
isolated, cached, and the tool must keep working without it if no backend is available.

`claude -p` (Claude Code CLI) was considered and rejected as the backend: this tool runs
unattended on SwiftBar's refresh timer (ADR 0004), and an automated Claude Code call inside
that loop would consume usage quota without an explicit user action each time, and would need
Anthropic account auth — both break the "local, auth-free" sink principle harder than any of
the alternatives below.

### Bake-off

Three backends were run head-to-head against six real workbench folders (identical prompt,
identical README/manifest/commit context per folder), as a throwaway spike under
`~/Desktop/YOLO-WORKBENCH/folder-describe-spike/`:

| Backend | Ø runtime | Cost | Result |
|---|---|---|---|
| **Apple Intelligence** (native, `FoundationModels` framework) | 1.3–3.0s | free, on-device | precise, concise, no hallucinations across all 6 folders |
| MLX (Qwen2.5-3B-Instruct-4bit, local) | 1.4–2.4s | free, but ~1.6GB model download | comparable quality, marginally more verbose |
| Pi + Azure Foundry (`o4-mini`) | 4–10s | small but non-zero, cloud | slightly more verbose, network round-trip |

All three produced accurate, ungrounded-fact-free German one-liners for every test folder —
unlike an earlier informal test of Apple Intelligence that had hallucinated on one of three
folders. This run is what the decision below is based on, not the earlier one.

## Decision

- **Apple Intelligence is the sole primary backend** (`tools/describe_apple.swift`, invoked via
  `swift tools/describe_apple.swift "<context>"`). Fastest, free, on-device, no extra model
  download, and more than sufficient for a 20-word summary sentence.
- **Pi + Azure Foundry (`o4-mini`) is the fallback**, used only when Apple Intelligence is
  unavailable (non-Apple-Silicon device, feature disabled, framework missing, or the swift call
  errors/returns empty). Invoked as `pi -p --no-tools --no-session --model foundry-chat/o4-mini
  "<prompt>\n\n<context>"`, reusing an already-provisioned Foundry sandbox — no new cloud
  resource for this feature.
- **MLX is not adopted.** Comparable quality to Apple Intelligence but requires its own model
  download and a Python ML dependency stack — a third backend that adds footprint without
  adding capability, since Apple Intelligence already covers the same ground on the same
  hardware.
- **Isolated, cached, optional module (`descriptions.py`):**
  - Own cache file `descriptions.json`, *not* embedded in `state.json` — `state.json`'s schema
    (the contract to the SwiftBar consumer, ADR 0004) stays untouched.
  - Regeneration only on cache-miss: a folder's signal (README excerpt, `package.json`/
    `pyproject.toml` description, last commit subject + remote, or a directory listing as last
    resort) is hashed; unchanged hash → reuse the cached sentence, no backend call.
  - Budgeted per run (`JANITOR_MAX_NEW_DESCRIPTIONS`, default 5) so a bulk import of new
    folders can't stall the SwiftBar refresh (every 30 min) for minutes — the rest catch up
    over subsequent runs.
  - Graceful degradation: neither backend available → the step is skipped entirely, the rest of
    `janitor.py` runs unaffected. `--skip-descriptions` forces this manually.

## Consequences

- The core classification pipeline remains exactly as deterministic and LLM-free as ADR 0001
  describes; the new capability is opt-in by backend availability, not by design coupling.
- No Claude Code / Anthropic account dependency was introduced into an unattended background
  tool.
- A machine without Apple Silicon (or with Apple Intelligence disabled) still gets
  descriptions, just slower and via a small, non-zero-cost cloud call — visible in the
  dashboard via each entry's `backend` field (`"apple"` vs `"pi-foundry"`).
- One more moving part to know about when debugging: if descriptions stop updating, check
  `swift -version`/`SystemLanguageModel.default.isAvailable` and `pi` availability before
  suspecting `descriptions.py` itself.
