# CortexLLM Roadmap

This document tracks all planned features, active milestones, and implementation checklists for CortexLLM. Items are ordered by priority within each milestone. Checked items are complete and live on `main`.

---

## Current Version: 0.3.0 (Active)

### Milestone 0.3.0 — Stability & Core Architecture

Focus: fix foundational reliability issues before adding features.

#### Installer (`install.sh`)
- [x] Remove single-quoted heredoc delimiters so `$INSTALL_DIR`, `$CONFIG_DIR`, `$BIN_DIR` expand correctly
- [x] Remove `setup.py install` fallback; standardize on `pip3 install -e .`
- [x] Let `go build` fail loudly instead of swallowing errors with `2>/dev/null`
- [x] Make `cortex-inject` read model/endpoint from `config.json` instead of hardcoding values
- [ ] Add PEP 668 guard — create a venv in `$INSTALL_DIR` if global pip install is blocked
- [ ] Validate generated `config.json` with `python3 -c "import json; json.load(open(...))"` before writing

#### Memory Schema (`memory.py`, `memory-tools.py`, migration scripts)
- [x] Enforce one canonical on-disk schema for HOT memory (flat list of `MemoryEntry` objects)
- [x] Replace all bare `except: pass` blocks with specific exception types and logging
- [ ] Unify HOT schema across Go (`main.go`) and Python writers — Go currently writes a plain list; Python migration scripts write a session-wrapper object
- [ ] Make `migrate-external-memory.py` write to a named file (not `openclaw.json`) to prevent attribution overwrite
- [ ] Add atomic-write guard to all migration scripts (write to `.tmp`, rename on success)

#### Python Backend (`brain.py`, `watch.py`)
- [x] Add `start()`, `stop()`, and `_drain_queue()` to `Brain` so queued tasks are actually executed
- [x] Add `mode` key to `Brain.status()` return value
- [x] Remove dead imports from `watch.py` (`curses`, `threading`, `os`)
- [x] Remove duplicate screen-clear from `watch.py`
- [ ] Replace blocking `input()` calls in `watch.py` with async-safe alternatives
- [ ] Reuse `aiohttp.ClientSession` across health checks instead of creating a new session per call
- [ ] Make dashboard redraw event-driven (only repaint on state change, not every second)
- [ ] Add backoff/jitter to 10-second platform polling in `watch.py`

#### Packaging (`pyproject.toml`)
- [x] Fix author email (was `github.com/greyok00`, must be valid RFC 5322)
- [x] Add `aiohttp>=3.9.0` and `aiofiles>=23.0.0` to `dependencies`
- [x] Bump version to `0.3.0`
- [ ] Add remaining runtime dependencies (`fsnotify` equivalent for Python watcher, any scraping libs)

---

## Milestone 0.4.0 — Multi-Agent Routing & Downstepping

Focus: make the Brain's model routing explicit, configurable, and testable.

### RouterConfig
- [ ] Define `RouterConfig` dataclass with fields: `reasoning_model`, `reasoning_host`, `reasoning_token_cap`, `worker_model`, `worker_host`, `worker_token_cap`
- [ ] Load `RouterConfig` from `config.json` at startup; fall back to env vars (`REASONING_MODEL`, `WORKER_MODEL`, etc.)
- [ ] Apply per-slot token caps before sending to any model — truncate context to `token_cap` if over limit

### Downstepping
- [ ] Route all tasks flagged `task_type=reasoning` to the reasoning slot
- [ ] Route all tasks flagged `task_type=worker` to the worker slot (cheaper/faster model)
- [ ] Default routing policy: reasoning slot = `gpt-oss:20b-cloud`, worker slot = `deepseek-v3.1:671b-cloud`; both via local Ollama daemon
- [ ] Expose `--reasoning-model` and `--worker-model` CLI flags for quick override without editing config

### Multi-Agent
- [ ] Support N named workers per session (not just OpenCode + OpenClaw)
- [ ] Each worker is independently routable: own model, own host, own token cap
- [ ] Per-worker `kill` command: stop one worker without killing others
- [ ] `kill-all` command: stop all active workers cleanly
- [ ] Per-worker heartbeat: 429 / rate-limit responses pause that worker only, not the whole session
- [ ] Worker rename: allow any worker to be renamed at runtime (e.g., `opencode` → `planner-1`)

### Warm Memory Scaling
- [ ] Remove hardcoded 2-model assumption from warm memory buffer calculation
- [ ] Auto-compute per-model buffer floor: `warm_buffer_pct / N` where N is the number of active models
- [ ] With 2 models: 70% recent, 30% buffer (15% each); with 4 models: 70% recent, 30% buffer (7.5% each)
- [ ] Recompute buffer allocation dynamically when workers are added or removed mid-session

---

## Milestone 0.5.0 — Cloud Router, Scheduled Workers & Memory Export

Focus: first-class support for non-Ollama cloud providers, automation via scheduled workers, and human-readable memory exports.

### Cloud API Router
- [ ] Add `provider` field to each router slot config: `"ollama"` (default), `"openai"`, `"anthropic"`, `"gemini"`
- [ ] Each provider gets its own adapter that normalizes the request/response shape to the internal `ModelResponse` interface
- [ ] `OllamaAdapter` — existing local-daemon path (`http://127.0.0.1:11434`); supports `-cloud` suffixed model names
- [ ] `OpenAIAdapter` — reads `OPENAI_API_KEY` env var; targets `https://api.openai.com/v1/chat/completions`
- [ ] `AnthropicAdapter` — reads `ANTHROPIC_API_KEY`; targets `https://api.anthropic.com/v1/messages`
- [ ] `GeminiAdapter` — reads `GEMINI_API_KEY`; targets `https://generativelanguage.googleapis.com/v1beta/`
- [ ] If provider API key env var is unset, log a clear error and refuse to start that slot (no silent fallback)
- [ ] Add provider + model to worker status output so it's always visible which backend is active
- [ ] Update `config.json` schema: `router.reasoning_provider`, `router.worker_provider` fields
- [ ] Document all four providers in README with example config snippets

### Scheduled / Cron Workers
- [ ] Add `schedule` field to worker config: accepts cron expression (`"0 */6 * * *"`) or interval shorthand (`"6h"`, `"30m"`)
- [ ] Implement `SchedulerService` that parses schedule fields on startup and registers cron jobs
- [ ] Each scheduled job spawns a named worker with a pre-defined task payload from config
- [ ] Scheduled workers run headlessly — output goes to a dedicated log file and optionally to HOT memory
- [ ] Skip execution if a previous run of the same worker is still active (no overlapping runs)
- [ ] Add `cortexllm schedule list` CLI command to show all registered jobs and their next run time
- [ ] Add `cortexllm schedule run <name>` to trigger a scheduled worker immediately on demand
- [ ] Add `scheduler_enabled: true/false` top-level config flag

### Memory Export
- [ ] Add `cortexllm memory export` CLI command
- [ ] `--format md` (default) — renders cold vault as a structured Markdown document grouped by `record_type`
- [ ] `--format pdf` — converts the Markdown export to PDF via `weasyprint` or `pandoc` (auto-detected at runtime)
- [ ] `--filter <tag>` — export only records matching a given tag
- [ ] `--since <date>` — export only records created or updated after a given date (ISO 8601)
- [ ] Output file defaults to `~/cortexllm-memory-export-<timestamp>.md` unless `--output` is specified
- [ ] Export includes a header with export timestamp, total record count, and active model slots
- [ ] Each exported record includes: entity, record_type, summary, detail, tags, confidence, last_seen_at

---

## Milestone 0.6.0 — DOM Pruning & Browser Worker

Focus: reduce token waste and noise from browser/scraper workers.

### `prune_dom_to_semantic_markdown` helper
- [ ] Strip from fetched HTML: `<script>`, `<style>`, `<svg>`, `<noscript>`, `<iframe>`, ad/tracking selectors, cookie banners, site headers/footers, navigation menus
- [ ] Convert remaining semantic content to clean Markdown (headings, paragraphs, lists, code blocks, tables)
- [ ] Return pruned Markdown string — caller decides whether to store in HOT memory or pass directly to model
- [ ] Target output: ≤20% of original raw HTML byte count for typical news/docs pages

### Worker Pipeline Integration
- [ ] Call `prune_dom_to_semantic_markdown` in OpenClaw's browser fetch path before any content hits the context window
- [ ] Apply pruning before content is written to HOT memory from browser tools
- [ ] Add `dom_pruning: true/false` flag to worker config so it can be disabled per-worker
- [ ] Log token savings per fetch (raw tokens vs. pruned tokens) in the worker status output

### SEARCH FIRST Enforcement
- [ ] Implement SEARCH FIRST check as a Brain-level pre-execution hook
- [ ] Workers that skip verification steps are flagged and retried with a verification prompt
- [ ] Add `search_first_verified: bool` field to task records so auditing is possible

---

## Milestone 0.7.0 — Background Promoter (Dreamer)

Focus: make the cold vault useful by automatically promoting durable knowledge from warm memory.

### `BackgroundPromoter` class (`brain.py`)
- [ ] Async worker that sleeps for `check_interval_seconds` (default 60), then runs a consolidation pass
- [ ] Consolidation pass: read warm memory deltas → score candidates → promote qualifying items to cold vault → update indexes
- [ ] Promotion threshold: an item promoted if `confirmation_count >= 3` or manually flagged
- [ ] Runs in a background thread with its own asyncio event loop so it never blocks the main interaction loop
- [ ] Respects `promoter_enabled: true/false` in config

### COLD Vault Schema Enforcement
- [ ] Every cold vault write must include all required fields: `id`, `entity`, `record_type`, `summary`, `detail`, `source_kind`, `confidence`, `tags`, `status`, `created_at`, `last_seen_at`
- [ ] `record_type` must be one of: `fact`, `preference`, `workflow`, `decision`, `lesson`
- [ ] `source_kind` must be one of: `user`, `tool`, `system`, `agent_inferred`
- [ ] Reject writes that fail schema validation; log the rejection with the offending payload
- [ ] Support `status` transitions: `active` → `superseded` when a newer conflicting record is promoted

### Session Heartbeat (`SessionHeartbeat` class)
- [ ] Runs synchronously before every agent turn
- [ ] Checks for stale session lock; unlocks and logs if stale
- [ ] Flushes pending HOT writes (debounce: only write if dirty flag is set)
- [ ] Rehydrates prompt context: HOT entirely, WARM partially, top COLD vault hits injected by keyword/tag match
- [ ] Returns structured context dict: `{"hot": [...], "warm": [...], "vault": [...]}`

---

## Milestone 0.8.0 — TUI Polish

Focus: incremental TUI improvements that do not require a full rewrite. Heavy TUI changes (tabbed layout, Workers Dashboard, thinking display) are deferred to 0.9.0.

### Performance
- [ ] Replace `exec.Command("curl", ...)` in `main.go` health checks with a shared `http.Client`
- [ ] Replace `exec.Command("sqlite3", ...)` with a Go SQLite driver or lazy import
- [ ] Debounce saves with a dirty flag and timer; stop writing every 2 seconds if nothing changed
- [ ] Cache rendered chat content when viewport state has not changed

### Correctness
- [ ] Unify HOT memory write format between Go and Python (single canonical schema)
- [ ] Add `is_last_command` tracking per platform for seamless platform switching
- [ ] Fix screen-clear to use ANSI escape only (no `os.system("clear")`)

### Theme
- [ ] Persist selected theme to `config.json` so it survives restarts
- [ ] Add at least two additional built-in themes

---

## Milestone 0.9.0 — TUI Overhaul (Tabbed Multi-Worker Layout)

Focus: full tabbed layout, Workers Dashboard, and thinking display. This is the large TUI change deferred from 0.8.0.

### Primary Views
- [ ] **Chat view** — main interaction pane, full message history, per-model color coding
- [ ] **Workers Dashboard** — left panel: list of active workers with status indicator; right panel: selected worker detail form; bottom bar: keybinds
- [ ] **Token Dashboard** — global and per-worker token usage widget with session totals

### Tabbed Layout
- [ ] Each active worker gets its own tab: Main, Code-1, Claw-1, etc.
- [ ] Per-tab output buffers — switching tabs does not lose scroll position
- [ ] Keyboard: `Alt+Left / Alt+Right` or `F1–F4` to change tabs
- [ ] Tab label shows worker name + current model shortname + status dot

### Thinking Display
- [ ] Show summarized reasoning steps in a collapsible panel below the active message
- [ ] Code blocks in thinking display are hidden by default; toggle with `c`
- [ ] Hard cap on thinking display lines (default: 10 lines); overflow truncated with a "show more" indicator
- [ ] Thinking display panel can be fully collapsed with `t`

### Worker Controls
- [ ] `K` — kill selected worker
- [ ] `Shift+K` — kill all workers
- [ ] `R` — rename selected worker
- [ ] `N` — spawn new worker (prompts for model and name)

---

## Milestone 1.0.0 — Android / Termux Distribution

Focus: make CortexLLM usable on Android without requiring a desktop environment.

### Option A: Termux Distribution
- [ ] Confirm Termux install instructions are accurate (F-Droid preferred; do not mix F-Droid and Play Store installs)
- [ ] Add `install-android.sh` that handles Termux-specific package names (`pkg install golang python`)
- [ ] Add `Termux:Widget` shortcut script that execs the CortexLLM TUI from the Android home screen
- [ ] Document Termux:Widget setup in `docs/android.md`

### Option B: Standalone Android App
- [ ] Fork Termux app source; strip unnecessary terminal emulation layers
- [ ] Embed pre-compiled `cortex-tui` ARM64 binary in `app/src/main/assets/`
- [ ] Bootstrap script execs binary on app launch: `nativeLibraryDir/cortex-tui`
- [ ] Cross-compile command: `GOOS=android GOARCH=arm64 go build -o cortex-tui ./main.go`
- [ ] Note: if cgo or NDK libs are needed, add Android NDK toolchain and CGO flags to build instructions
- [ ] Sign APK and document sideload instructions

---

## Deferred / Under Consideration

These items are noted but not yet assigned to a milestone.

- **Vector/embedding index for COLD vault** — local embedding-based retrieval for large cold stores
- **Web UI** — optional browser-based dashboard for non-terminal users
- **Structured task queue with priorities** — replace current FIFO queue with a priority queue
- **Plugin system** — allow external workers to register themselves via a socket or named pipe

---

## Completed (Shipped in 0.1.0 – 0.2.0)

- [x] Basic Bubble Tea TUI with 2-pane layout
- [x] Hot/Warm/Cold memory tier implementation
- [x] Atomic temp-file + rename writes
- [x] Auto-unlock system for stale session locks
- [x] OpenCode and OpenClaw platform integration
- [x] Install script (`install.sh`)
- [x] Heredoc variable expansion fix
- [x] `go build` error transparency
- [x] `setup.py` install fallback removal
- [x] `cortex-inject` reads config dynamically
- [x] `Brain.start()`, `stop()`, `_drain_queue()` implemented
- [x] `Brain.status()` returns `mode` key
- [x] Dead imports removed from `watch.py`
- [x] Duplicate screen-clear removed from `watch.py`
- [x] `pyproject.toml` author email fixed
- [x] Runtime dependencies declared in `pyproject.toml`
- [x] Version bumped to `0.3.0`

---

*Last updated: 2026-06-27 — [@greyok00](https://github.com/greyok00)*
