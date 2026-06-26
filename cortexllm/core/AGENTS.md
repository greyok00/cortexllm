# CortexLLM - Brain-First Multi-Agent System

**Version:** 2026.6.23

## What is CortexLLM?

CortexLLM is a **Brain-First Multi-Agent System** that lets you:
- Create specialized **workers** for different tasks
- Run tasks in **parallel** with automatic coordination
- Maintain **persistent memory** across sessions
- Resume work from where you left off

---

## Quick Start

**Submit a task:**
```python
from cortexllm import Brain
brain = Brain()
task = brain.submit("research Python async best practices")
```

**The Brain will:**
1. Analyze your request
2. Select appropriate workers
3. Execute in parallel
4. Save results to memory

---

## Architecture

```
Your Request → Brain → Workers → Memory
                ↓
         [research-worker]
         [code-worker]
         [write-worker]
```

---

## Workers

Workers are specialized agents that handle specific types of tasks.

### Built-in Workers

| Worker | Handles | Keywords |
|--------|---------|----------|
| research | Web research, data gathering | "research", "search", "find" |
| code | Programming, debugging | "code", "program", "debug" |
| write | Content writing | "write", "draft", "compose" |
| general | Fallback for everything else | (any) |

### Creating Custom Workers

Create a file `my_custom_worker.py`:

```python
from cortexllm.workers import Worker
import asyncio

class DataAnalysisWorker(Worker):
    """Analyzes data and generates reports"""
    
    def __init__(self):
        super().__init__("data-analysis", "analytics")
    
    async def run(self, task_input: str) -> str:
        # Your logic here
        await asyncio.sleep(1)  # Simulate work
        return f"Analysis complete for: {task_input}"
```

Register it:
```python
from cortexllm.workers import register_worker
from my_custom_worker import DataAnalysisWorker

register_worker("data-analysis", DataAnalysisWorker)
```

Now use it:
```python
task = brain.submit("analyze sales data")  # Uses data-analysis worker
```

---

## Memory System

### How It Works

CortexLLM saves everything to `~/.config/cortexllm/`:

- **Tasks:** What you asked for and results
- **Sessions:** Context and state
- **Workers:** Custom worker definitions

### Memory Structure

```
~/.config/cortexllm/
├── config.json       # Your settings
├── tasks.json        # Task history
├── session.json      # Current session
└── memories.jsonl    # Learned patterns
```

### Cross-Platform Resume

Start in **OpenCode**, resume in **OpenClaw**:

```python
# In OpenCode
brain = Brain()
brain.submit("long running research task")

# Later in OpenClaw
brain = Brain()
brain.resume()  # Continues where you left off
```

---

## Features

### Mode Switching

Tasks automatically detected as **BACKGROUND** or **FOREGROUND**:

- **Background:** Research, data gathering (runs async)
- **Foreground:** Form submissions, purchases (requires approval)

### Parallel Execution

Multiple workers run simultaneously:

```python
# This uses both research and code workers in parallel
task = brain.submit("research Python and code a solution")
```

### Session Persistence

Your work is automatically saved:
- Tasks never lost
- Resume after restart
- Cross-platform compatible

---

## Configuration

Edit `~/.config/cortexllm/config.json`:

```json
{
  "brain": {
    "heartbeat_interval": 30,
    "task_timeout": 300
  },
  "workers": {
    "max_concurrent": 10
  },
  "browser": {
    "cdp_url": "http://127.0.0.1:9222"
  },
  "search": {
    "base_url": "http://127.0.0.1:8888"
  }
}
```

---

## API Reference

### Brain

```python
brain = Brain()
brain.submit("task description")  # Submit task
brain.status()                     # Get system status
brain.resume()                     # Resume session
```

### Memory

```python
mem = Memory()
mem.session()                      # Get current session
mem.tasks()                        # List all tasks
mem.save_task("id", {...})         # Save task data
```

### Config

```python
cfg = Config()
cfg.get("brain", "task_timeout")   # Get setting
cfg.set("brain", "task_timeout", value=600)  # Set setting
```

---

## Examples

### Basic Research

```python
brain = Brain()
task = brain.submit("research async Python patterns")
# Result saved to memory
```

### Custom Domain

```python
# Create medical research worker
class MedicalWorker(Worker):
    def __init__(self):
        super().__init__("medical", "healthcare")
    
    async def run(self, task_input):
        # Search medical databases
        return f"Medical research: {task_input}"

register_worker("medical", MedicalWorker)

# Use it
task = brain.submit("research diabetes treatments")
```

### Session Management

```python
# Start session
brain = Brain()
brain.submit("task 1")
brain.submit("task 2")

# Save explicitly
mem = Memory()
mem.session({"platform": "opencode", "context": "work"})

# Resume later
brain.resume()  # Loads session
```

---

## Troubleshooting

**Task not completing?**
- Check `brain.status()` for worker health
- Check `mem.tasks()` for task status

**Worker not found?**
- Ensure worker is registered with `register_worker()`
- Check worker ID matches keywords in task

**Session not resuming?**
- Verify `~/.config/cortexllm/session.json` exists
- Check session has valid platform field

---

## Support

For issues and feature requests, see the documentation at:
https://github.com/yourusername/cortexllm

---

**Next Steps:**
1. Try submitting a task
2. Create a custom worker
3. Resume a session in different platform
