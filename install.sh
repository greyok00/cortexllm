#!/bin/bash
# install.sh — set up CortexLLM for the current user.
#
# - Creates the standalone memory dir (~/.cortexllm/memory)
# - Marks scripts executable
# - Renders config templates with $HOME paths
#
# No hardcoded home paths; everything is $HOME-relative. Re-runnable.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEMORY_DIR="${CORTEXLLM_MEMORY_DIR:-$HOME/.cortexllm/memory}"
CONFIG_DIR="${CORTEXLLM_CONFIG_DIR:-$HOME/.cortexllm-config}"

echo "==> CortexLLM install — ${REPO_ROOT}"
echo "    memory dir: ${MEMORY_DIR}"
echo "    config dir: ${CONFIG_DIR}"

MEMORY_CMD="python3 ${REPO_ROOT}/memory/mcp_server.py"

# ── Make scripts executable ─────────────────────────────────────────────────
chmod +x "${REPO_ROOT}/hooks/"*.sh \
        "${REPO_ROOT}/memory/"*.py \
        "${REPO_ROOT}/lib/"*.py \
        "${REPO_ROOT}/lib/"*.sh 2>/dev/null || true
echo "    scripts made executable"

# ── Standalone memory dir ───────────────────────────────────────────────────
mkdir -p "${MEMORY_DIR}"
echo "    memory dir: ${MEMORY_DIR}"

# ── Render config templates ─────────────────────────────────────────────────
mkdir -p "${CONFIG_DIR}"

# mcp.json
python3 - "${REPO_ROOT}/config" "${CONFIG_DIR}" "${MEMORY_CMD}" <<'PY'
import json, os, sys
config_dir, isolated_dir, memory_cmd = sys.argv[1], sys.argv[2], sys.argv[3]
tpl = json.load(open(os.path.join(config_dir, "mcp.json.template")))
tpl["mcpServers"]["cortexllm"]["command"] = memory_cmd
raw = json.dumps(tpl, indent=2)
raw = raw.replace("{{REPO_ROOT}}", os.path.dirname(os.path.dirname(memory_cmd)))
open(os.path.join(isolated_dir, "mcp.json"), "w").write(raw + "\n")
print(f"    wrote {os.path.join(isolated_dir, 'mcp.json')}")
PY

# settings.json
python3 - "${REPO_ROOT}/config" "${CONFIG_DIR}" "${HOME}" <<'PY'
import os, sys
config_dir, isolated_dir, home = sys.argv[1], sys.argv[2], sys.argv[3]
raw = open(os.path.join(config_dir, "settings.json.template")).read()
raw = raw.replace("{{HOME}}", home)
open(os.path.join(isolated_dir, "settings.json"), "w").write(raw)
print(f"    wrote {os.path.join(isolated_dir, 'settings.json')}")
PY

# CLAUDE.md
cp "${REPO_ROOT}/config/CLAUDE.md" "${CONFIG_DIR}/CLAUDE.md" 2>/dev/null || true

echo ""
echo "Done. Set CORTEXLLM_REPO=${REPO_ROOT} in your environment."
echo "Add to your Claude Code config:"
echo "  --mcp-config ${CONFIG_DIR}/mcp.json"
echo "  --config-dir ${CONFIG_DIR}"
