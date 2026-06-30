# CortexLLM Production Config for OpenClaw

This package contains production-ready configuration overrides for OpenClaw.

## What's Included

- **workspace/SOUL.md** - Core agent rules with anti-hallucination protocols
- **workspace/AGENTS.md** - Detailed agent instructions with TOS compliance
- **production/platforms/** - Platform-specific configs for OpenClaw, Claude, OpenCode
- **openclaw.json.config** - Base configuration template (customize token before use)

## Installation

Copy contents to your OpenClaw installation:

```bash
# From CortexLLM repo root
cd cortexllm/production/openclaw

# Copy workspace configs (SOUL.md, AGENTS.md)
cp -r workspace/* ~/.openclaw/workspace/

# Copy production platform configs
cp -r production/* ~/.openclaw/production/

# Copy and customize config
cp openclaw.json.config ~/.openclaw/openclaw.json
# EDIT ~/.openclaw/openclaw.json and set your auth token
```

## Key Features

### Anti-Hallucination Protocol
- PRE-FLIGHT: Snapshot before any browser action
- Must verify before claiming limitations
- Retry 3x before reporting failure

### Quiz/Form Protocol  
- Read actual question from snapshot
- Extract EXACT content before answering
- Never invent question content

### TOS Compliance
- Check TOS before automating survey/review sites
- Respect timing requirements (2-3 min per task)
- Complete ALL required fields (60+ word reviews)
- Stop at CAPTCHA, warnings, rate limits

### Red Flags (Auto-Stop)
- Account locked/banned messages
- "Suspicious activity" warnings
- CAPTCHA challenges
- "Verify you're human" messages

## Version

v0.2 - Anti-hallucination and TOS compliance update
