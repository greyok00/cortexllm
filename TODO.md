# CORTEXLLM PROJECT TODO LIST
## Version: 0.2.0 - In Development

> ⚠️ **Status: Active Development** — core memory and TUI are functional; several items below are not yet complete. Do not treat this as production-ready until the 0.2.0 checklist is fully satisfied.

---

## ✅ COMPLETED

### Memory Persistence
- [x] Atomic writes (temp file + rename) in Go TUI
- [x] Auto-save every 2 seconds (tick-based)
- [x] Save on quit (Esc/Ctrl+C)
- [x] Save on message send (user + AI)
- [x] Full session recovery on startup
- [x] Python memory.py atomic writes
- [x] Unified path: `~/.config/cortexllm/`

### Platform Integration
- [x] OpenCode via Ollama (`opencode run`)
- [x] Claude via Ollama API
- [x] OpenClaw via Ollama API
- [x] Platform health monitoring
- [x] Independent per-platform state

### Go TUI Features
- [x] Bubble Tea framework
- [x] 3-pane layout (Sidebar | Chat | Diagnostics)
- [x] Tab switching (OpenCode/Claude/OpenClaw/Memory)
- [x] 7 themes
- [x] Theme picker (Ctrl+T)
- [x] Config overlay (Ctrl+P)
- [x] 60 FPS animations
- [x] Viewport scrolling
- [x] Input handling (space, backspace, enter)

### Python API
- [x] Brain class (task submission + lifecycle via `start()`/`stop()`)
- [x] Brain task queue drain (`_drain_queue` loop)
- [x] Memory class (atomic persistence)
- [x] Config class (unified config)
- [x] Worker system (research, code, write, general)
- [x] Proper `__init__.py` exports

### Configuration
- [x] Unified config at `~/.config/cortexllm/config.json`
- [x] Auto-create directories on startup
- [x] Default config generation (paths expand correctly via install.sh)
- [x] Browser CDP integration
- [x] Searxng search integration
- [x] OpenClaw gateway support

### Build & Deploy
- [x] Go 1.24.2 compatibility
- [x] go.mod with all dependencies
- [x] install.sh script (heredoc variable expansion fixed)
- [x] Proxy build errors surface correctly (not swallowed)
- [x] Python installer uses pip3 only (setup.py fallback removed)

---

## 🔴 OPEN — Must Close Before 0.2.0 Tag

### Critical
- [ ] Remove compiled binary `cortexllm/main` from Python package directory (breaks pip on non-matching arch; add to .gitignore and document manual build step)
- [ ] Fix README install URL — points to `scripts/install.sh` but file is in repo root (`install.sh`)
- [ ] Fix README build-from-source `cd cortexllm` — `main.go` is in repo root, not inside the Python package folder

### Memory System
- [ ] Enforce single canonical schema for cold/warm/hot (cold archives wrap in `{Messages:[]}` dict; warm is a flat list — must align)
- [ ] Replace bare `except: pass` in `memory-tools.py` `append_message()` with `except (FileNotFoundError, json.JSONDecodeError)`
- [ ] Auto-rotation at 50 messages (hot tier)
- [ ] Token counting (8k limit enforcement)
- [ ] Session summaries before cold archive
- [ ] Warm memory sync (unified.json) finalized

### Advanced Features
- [ ] Multi-step task planning
- [ ] Background/foreground task modes
- [ ] Task approval workflow
- [ ] Cross-platform session merge
- [ ] Configurable downstepping: reasoning model slot vs. worker model slot
- [ ] DOM pruning helper (`prune_dom_to_semantic_markdown`) for browser workers

### Testing
- [ ] Unit tests for Go TUI
- [ ] Async integration tests for Brain start/stop/queue drain
- [ ] Performance benchmarks
- [ ] Memory leak detection

---

## CURRENT STATUS

| Component | Status | Notes |
|-----------|--------|-------|
| Go TUI | ✅ Functional | Persistence working |
| Python API | ⚠️ In Progress | `start()`/`stop()`/queue drain fixed; needs test coverage |
| Proxy | ✅ Functional | Message injection works |
| Memory System | ⚠️ In Progress | Hot tier functional; cold/warm schema drift open |
| Documentation | ⚠️ In Progress | README install URLs need fixing |
| Installation | ⚠️ In Progress | Heredoc quoting fixed; binary-in-package issue open |

---

## DIRECTORY STRUCTURE

```
<repo root>/
├── main.go                      ← Go TUI source (build from here)
├── proxy/main.go                ← Message proxy
├── install.sh                   ← Installer (run from repo root)
├── cortexllm/                   ← Python package
│   ├── core/
│   │   ├── brain.py             ← Task orchestration + queue drain
│   │   ├── memory.py            ← Atomic persistence
│   │   ├── config.py            ← Config handler
│   │   └── orchestrator.py      ← Worker routing (consolidation with brain.py pending)
│   ├── workers/__init__.py      ← Worker definitions
│   ├── cli/unified.py           ← CLI tools
│   └── __init__.py              ← Python exports
├── memory-tools.py              ← Standalone memory CLI
├── watch.py                     ← Real-time monitor
├── go.mod / go.sum              ← Go dependencies
├── pyproject.toml               ← Python package config
└── *.md                         ← Documentation

~/.config/cortexllm/             ← Runtime data
├── config.json
├── session.json
├── tasks.json
└── memory/
    ├── hot/
    ├── warm/
    └── cold/
```
