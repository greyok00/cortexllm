#!/usr/bin/env python3
"""
CortexLLM Orchestrator - Goal receiver and task dispatcher
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

class Orchestrator:
    """Receives top-level goals, breaks them into tasks, assigns workers"""

    def __init__(self, memory_path: str = "~/.config/cortexllm"):
        self.mem_path = Path(memory_path).expanduser()
        self.checkpoint_dir = self.mem_path / "checkpoints"
        self.action_log = self.mem_path / "action-log.md"
        self.workers: Dict[str, dict] = {}
        self.active_tasks: List[dict] = []

        self._ensure_dirs()

    def _ensure_dirs(self):
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.mem_path.mkdir(parents=True, exist_ok=True)

    def receive_goal(self, goal_type: str, params: dict) -> dict:
        task_id = f"{goal_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        task = {
            "id": task_id,
            "type": goal_type,
            "status": "queued",
            "params": params,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "worker_type": self._get_worker_type(goal_type),
            "progress": {"total": 0, "completed": 0}
        }

        self._save_checkpoint(task_id, "goal_received", task)
        self.active_tasks.append(task)

        return task

    def _get_worker_type(self, goal_type: str) -> str:
        mapping = {
            "research": "research-worker",
            "code": "code-worker",
            "write": "write-worker",
            "search": "research-worker",
            "analyze": "code-worker"
        }
        return mapping.get(goal_type, "general-worker")

    def _save_checkpoint(self, task_id: str, step: str, data: dict):
        """Atomically save checkpoint to disk"""
        checkpoint_dir = self.checkpoint_dir / task_id
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_file = checkpoint_dir / f"{timestamp}_{step}.json"
        tmp_file = checkpoint_file.with_suffix(".tmp")

        tmp_file.write_text(json.dumps(data, indent=2))
        tmp_file.replace(checkpoint_file)

        # Keep only last 20 checkpoints
        checkpoints = sorted(checkpoint_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        for old in checkpoints[:-20]:
            old.unlink()

    def dispatch_worker(self, task_id: str, worker_type: str) -> str:
        import random
        worker_id = f"{worker_type}_{random.randint(1000, 9999)}"

        worker = {
            "id": worker_id,
            "type": worker_type,
            "task_id": task_id,
            "status": "starting",
            "started_at": datetime.now(timezone.utc).isoformat()
        }

        self.workers[worker_id] = worker
        self._log_action(f"Dispatched {worker_id} for {task_id}")

        return worker_id

    def _log_action(self, description: str):
        timestamp = datetime.now(timezone.utc).isoformat()
        with open(self.action_log, "a") as f:
            f.write(f"- [{timestamp}] {description}\n")

    def get_status(self) -> dict:
        return {
            "active_workers": len([w for w in self.workers.values() if w["status"] == "running"]),
            "queued_tasks": len([t for t in self.active_tasks if t.get("status") == "queued"]),
            "total_tasks": len(self.active_tasks)
        }

    def complete_task(self, task_id: str):
        for task in self.active_tasks:
            if task["id"] == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.now(timezone.utc).isoformat()
                self._log_action(f"Task {task_id} completed")
                break
