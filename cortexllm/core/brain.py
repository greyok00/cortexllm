"""Brain - Core orchestrator"""
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum, auto

class Status(Enum):
    QUEUED = auto(); RUNNING = auto(); DONE = auto(); ERROR = auto()

class Mode(Enum):
    BACKGROUND = auto(); FOREGROUND = auto()

@dataclass
class Task:
    id: str; input: str; status: Status = Status.QUEUED; mode: Mode = Mode.BACKGROUND
    workers: List[str] = field(default_factory=list)
    created: float = field(default_factory=time.time)
    started: Optional[float] = None; done: Optional[float] = None
    result: Optional[str] = None; error: Optional[str] = None
    progress: int = 0

@dataclass
class WorkerState:
    id: str; domain: str; status: str = "idle"; last_ping: float = 0
    current_task: Optional[str] = None; tasks_completed: int = 0; tasks_failed: int = 0

class Brain:
    """Central orchestrator with Brave + searxng defaults"""
    
    CDP_URL = "http://127.0.0.1:9222"
    SEARXNG_URL = "http://127.0.0.1:8888"
    GATEWAY_PORT = 18789
    
    def __init__(self, config=None, memory=None):
        from .memory import Memory
        from .config import Config
        
        self.cfg = config or Config()
        self.mem = memory or Memory()
        
        self.CDP_URL = self.cfg.cdp_url
        self.SEARXNG_URL = self.cfg.searxng_url
        self.GATEWAY_PORT = self.cfg.gateway_port
        
        self.tasks: Dict[str, Task] = {}
        self.workers: Dict[str, WorkerState] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._callbacks: List[Callable] = []
        self.running = False
        
    def submit(self, text: str, ctx: Optional[Dict] = None) -> Task:
        ctx = ctx or {}
        mode = Mode.FOREGROUND if any(w in text.lower() for w in 
                                       ["submit","post","buy","approve","execute"]) else Mode.BACKGROUND
        
        task = Task(
            id=f"t{int(time.time()*1000)}",
            input=text,
            mode=mode,
            workers=self._select(text)
        )
        
        self.tasks[task.id] = task
        self._queue.put_nowait({"cmd": "run", "task": task, "ctx": ctx})
        self.mem.save_task(task.id, {"id": task.id, "input": text, "status": "queued", "created": task.created})
        return task
    
    def _select(self, text: str) -> List[str]:
        t = text.lower()
        workers = []
        if any(w in t for w in ["research","search","find"]):
            workers.append("research")
        if any(w in t for w in ["code","program","debug"]):
            workers.append("code")
        if any(w in t for w in ["write","draft"]):
            workers.append("write")
        return workers or ["general"]
    
    async def _execute(self, task: Task, ctx: Dict) -> None:
        task.status = Status.RUNNING; task.started = time.time()
        
        try:
            results = []
            for i, wid in enumerate(task.workers):
                result = await self._run_worker(wid, task); results.append(result)
                task.progress = int((i+1)/len(task.workers)*100)
            
            task.result = "\n".join(str(r) for r in results if r)
            task.status = Status.DONE; task.done = time.time()
        except Exception as e:
            task.status = Status.ERROR; task.error = str(e)
        finally:
            self.mem.save_task(task.id, self._task_to_dict(task))
    
    async def _run_worker(self, wid: str, task: Task) -> str:
        from ..workers import get_worker
        worker = get_worker(wid)
        if wid not in self.workers:
            self.workers[wid] = WorkerState(id=wid, domain=worker.domain)
        
        self.workers[wid].status = "busy"; self.workers[wid].current_task = task.id
        
        try:
            timeout = self.cfg.get("brain", "task_timeout", default=300)
            result = await asyncio.wait_for(worker.run(task.input), timeout=timeout)
            self.workers[wid].tasks_completed += 1; self.workers[wid].status = "idle"
            return result
        except asyncio.TimeoutError:
            self.workers[wid].tasks_failed += 1; self.workers[wid].status = "error"
            raise
    
    def _task_to_dict(self, task: Task) -> Dict:
        return {"id": task.id, "input": task.input, "status": task.status.name.lower(),
                "mode": task.mode.name.lower(), "workers": task.workers, "progress": task.progress,
                "result": task.result, "error": task.error, "created": task.created,
                "started": task.started, "done": task.done}
    
    def status(self) -> Dict:
        return {"running": self.running, "tasks": len(self.tasks), "workers": len(self.workers)}
    
    def resume(self) -> Optional[Task]:
        session = self.mem.session()
        if session:
            print(f"Resuming session from {session.get('platform', 'unknown')}")
        return session
