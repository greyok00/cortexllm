# Troubleshooting Guide

## TUI Won't Start

### Symptoms
```bash
$ cortexllm
bash: cortexllm: command not found
```

### Solutions

**Binary not installed:**
```bash
# Rebuild binary
cd ~/.openclaw/cortexllm
go build -o ~/.local/bin/cortexllm ./main.go

# Verify installation
ls -la ~/.local/bin/cortexllm
~/.local/bin/cortexllm --version
```

**Missing dependencies:**
```bash
# Check Go version
go version  # Should be 1.24+

# Install Go if needed
# https://go.dev/dl/
```

**Permission denied:**
```bash
chmod +x ~/.local/bin/cortexllm
```

## Platform Connection Issues

### OpenClaw Not Responding

**Symptoms:** TUI shows OpenClaw offline, or messages sent but no response.

**Check gateway status:**
```bash
curl http://127.0.0.1:18789/health
# Expected: {"status":"ok"}
```

**Gateway not running:**
```bash
# Restart gateway
systemctl --user restart openclaw-gateway

# Check status
systemctl --user status openclaw-gateway

# View logs
journalctl --user -u openclaw-gateway -f
```

**Token not set:**
```bash
# Check environment variable
echo $OPENCLAW_GATEWAY_TOKEN

# Set if empty
export OPENCLAW_GATEWAY_TOKEN=your_token_here

# Add to ~/.bashrc for persistence
echo "export OPENCLAW_GATEWAY_TOKEN=your_token_here" >> ~/.bashrc
source ~/.bashrc
```

**CLI test:**
```bash
# Test OpenClaw CLI directly
openclaw agent --agent brain --session-key cortexllm-test --message "hello" --json
```

### OpenCode Not Responding

**Symptoms:** OpenCode shows offline or messages fail.

**Check Ollama status:**
```bash
curl http://127.0.0.1:11434/api/tags
# Expected: {"models":[...]}
```

**Ollama not running:**
```bash
# Start Ollama
ollama serve

# In another terminal:
ollama pull qwen3.5:cloud
```

**Wrong endpoint:**
```bash
# Check config endpoint matches
jq '.platforms.opencode.endpoint' ~/.config/cortexllm/config.json

# Default: http://127.0.0.1:11434
```

**Model not available:**
```bash
# List available models
ollama list

# Pull required model
ollama pull qwen3.5:cloud
```

## Memory Issues

### Messages Not Saving

**Check directory permissions:**
```bash
ls -la ~/.config/cortexllm/memory/
chmod 755 ~/.config/cortexllm/memory
chmod 755 ~/.config/cortexllm/memory/hot
```

**Verify JSON files:**
```bash
# Check hot memory file
cat ~/.config/cortexllm/memory/hot/opencode.json | jq

# If corrupted, recreate
rm ~/.config/cortexllm/memory/hot/*.json
echo '[]' > ~/.config/cortexllm/memory/hot/opencode.json
echo '[]' > ~/.config/cortexllm/memory/hot/openclaw.json
```

**Disk space:**
```bash
df -h ~/.config
```

### SQLite Lock Issues

**Symptoms:** "database is locked" errors when loading OpenClaw sessions.

**Clear WAL files:**
```bash
rm -f ~/.openclaw/state/openclaw.sqlite-wal
rm -f ~/.openclaw/state/openclaw.sqlite-shm
```

**Restart gateway:**
```bash
systemctl --user restart openclaw-gateway
```

## Build Issues

### Go Build Fails

**Missing Go modules:**
```bash
cd ~/.openclaw/cortexllm
go mod tidy
go build -o ~/.local/bin/cortexllm ./main.go
```

**Module version mismatch:**
```bash
# Clear Go cache
go clean -cache -modcache

# Rebuild
go build -o ~/.local/bin/cortexllm ./main.go
```

### Python Install Fails

**pip not found:**
```bash
# Install pip
python3 -m ensurepip --upgrade
```

**Permission denied:**
```bash
# Use --user flag
pip3 install -e . --user
```

**Missing dependencies:**
```bash
# Install system packages (Debian/Ubuntu)
sudo apt install python3-dev python3-pip

# Or Fedora
sudo dnf install python3-devel python3-pip
```

## Theme/Display Issues

### Garbled Characters

**Terminal font issue:**
```bash
# Check terminal supports Unicode
echo "🧠 ⚡ 💡"

# Try different terminal
# Recommended: kitty, alacritty, wezterm, iTerm2
```

**Colors wrong:**
```bash
# Check TERM variable
echo $TERM

# Should be: xterm-256color, screen-256color, etc.
export TERM=xterm-256color
```

### Theme Not Loading

**Reset theme:**
```bash
# Theme is stored in TUI state
# Press Ctrl+T to cycle themes
# Restart TUI to reset to default (Sovereign)
```

## Search/Browser Issues

### Web Search Not Working

**Check Searxng:**
```bash
curl http://127.0.0.1:8888/health
```

**Searxng not running:**
```bash
# Start Searxng Docker
docker run -d -p 8888:8080 searxng/searxng

# Or test with public instance (not recommended for production)
# Update config: "base_url": "https://searx.be"
```

### Browser Automation Failing

**Check Brave CDP:**
```bash
curl http://127.0.0.1:9222/json/version
```

**Brave not running with CDP:**
```bash
# Start Brave with CDP enabled
brave --remote-debugging-port=9222 &
```

**Update config:**
```json
{
  "browser": {
    "enabled": true,
    "cdp_url": "http://127.0.0.1:9222"
  }
}
```

## Performance Issues

### TUI Laggy

**Reduce animation load:**
- Close other terminal applications
- Reduce terminal window size
- Use a lighter terminal emulator

**Check system resources:**
```bash
# CPU usage
top -p $(pgrep cortexllm)

# Memory usage
ps -o pid,rss,command -p $(pgrep cortexllm)
```

### Slow Responses

**Model too large:**
```bash
# Use smaller model as fallback
# Update config:
{
  "model": {
    "primary": "ollama/qwen3.5:cloud",
    "fallback": "ollama/llama3.1:8b"
  }
}
```

**Network latency (OpenClaw):**
```bash
# Test gateway latency
time curl http://127.0.0.1:18789/health
```

## Common Error Messages

### "OPENCLAW_GATEWAY_TOKEN not set"

**Solution:**
```bash
export OPENCLAW_GATEWAY_TOKEN=your_token_here
```

### "connection refused"

**OpenClaw:**
```bash
systemctl --user start openclaw-gateway
```

**Ollama:**
```bash
ollama serve
```

### "model not found"

```bash
ollama pull qwen3.5:cloud
```

### "permission denied"

```bash
chmod +x ~/.local/bin/cortexllm
chmod 755 ~/.config/cortexllm/memory
```

## Debug Mode

### Enable Verbose Logging

**Set environment variables:**
```bash
export CORTEXLLM_DEBUG=1
export DEBUG=1
cortexllm
```

### View TUI Logs

**Check stdout:**
```bash
# Run TUI and capture output
cortexllm 2>&1 | tee cortexllm.log
```

### Python Worker Logs

```bash
# Check worker logs
journalctl --user -u cortexllm-workers -f
```

## Getting Help

### Collect Debug Info

```bash
# System info
uname -a
go version
python3 --version

# CortexLLM version
~/.local/bin/cortexllm --version

# Config
cat ~/.config/cortexllm/config.json

# Memory structure
ls -la ~/.config/cortexllm/memory/

# Platform status
curl http://127.0.0.1:18789/health  # OpenClaw
curl http://127.0.0.1:11434/api/tags  # Ollama
```

### Report Issues

1. Collect debug info above
2. Check existing issues on GitHub
3. Create new issue with:
   - Description of problem
   - Expected behavior
   - Actual behavior
   - Debug info
   - Steps to reproduce
