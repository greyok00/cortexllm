#!/usr/bin/env python3
"""
CortexLLM Watch - Real-time monitoring and interaction
Integrated with OpenClaw for live task injection
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime
import curses
import threading
import time

# Use installed package path - no hardcoded paths

from cortexllm import Brain, Memory, Config

class CortexLLMWatch:
    """Real-time CortexLLM monitor with OpenClaw integration"""
    
    def __init__(self):
        self.mem = Memory()
        self.cfg = Config()
        self.brain = Brain(self.cfg, self.mem)
        self.running = True
        self.messages = []
        self.stdscr = None
        
    async def start(self):
        """Start watch mode"""
        print("="*70)
        print("CortexLLM WATCH - Real-Time Monitor")
        print("="*70)
        print("\nStarting brain and watch loops...")
        
        await self.brain.start()
        
        # Start background tasks
        await asyncio.gather(
            self._watch_loop(),
            self._input_loop()
        )
        
    async def _watch_loop(self):
        """Monitor and display status"""
        while self.running:
            os.system('clear' if os.name != 'nt' else 'cls')
            
            print("\033[2J\033[H")  # Clear screen
            print("="*70)
            print(f"CortexLLM WATCH - {datetime.now().strftime('%H:%M:%S')}")
            print("="*70)
            
            # System status
            status = self.brain.status()
            print(f"\nStatus: {'RUNNING' if status['running'] else 'STOPPED'}")
            print(f"Mode: {status['mode']}")
            print(f"Tasks: {status['tasks']}")
            print(f"Workers: {status['workers']} active")
            
            # Active tasks
            print("\n" + "-"*70)
            print("ACTIVE TASKS:")
            print("-"*70)
            tasks = self.mem.tasks()
            if tasks:
                for tid, t in list(tasks.items())[-5:]:  # Show last 5
                    status = t.get('status', 'unknown')
                    progress = t.get('progress', 0)
                    print(f"  {tid[:20]}... | {status:10} | {progress:3}% | {t.get('input', 'N/A')[:40]}")
            else:
                print("  No active tasks")
            
            # Message history
            print("\n" + "-"*70)
            print("MESSAGES:")
            print("-"*70)
            if self.messages:
                for msg in self.messages[-10:]:
                    print(f"  {msg}")
            else:
                print("  No messages")
            
            # Commands
            print("\n" + "="*70)
            print("COMMANDS:")
            print("  [r] Research    [s] Submit task    [q] Quit")
            print("  [b] Book search [c] Check status   [h] Help")
            print("="*70)
            
            await asyncio.sleep(1)
    
    async def _input_loop(self):
        """Handle user input"""
        while self.running:
            try:
                cmd = await asyncio.get_event_loop().run_in_executor(
                    None, input, "\nCommand: "
                )
                cmd = cmd.strip().lower()
                
                if cmd == 'q':
                    self.running = False
                    await self.brain.stop()
                    print("\nShutting down...")
                    break
                
                elif cmd == 'r':
                    task = self.brain.submit("research random interesting topic 2024")
                    self.messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] Research task: {task.id}")
                    print(f"✓ Research task submitted: {task.id}")
                
                elif cmd == 'b':
                    topic = input("Topic to find book about: ")
                    task = self.brain.submit(f"find book about {topic}")
                    self.messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] Book search: {task.id}")
                    print(f"✓ Book search submitted: {task.id}")
                
                elif cmd == 's':
                    custom = input("Task to submit: ")
                    task = self.brain.submit(custom)
                    self.messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] Custom task: {task.id}")
                    print(f"✓ Task submitted: {task.id}")
                
                elif cmd == 'c':
                    status = self.brain.status()
                    self.messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] Status: {status}")
                    print(f"Status: {status}")
                
                elif cmd == 'h':
                    print("\nHelp:")
                    print("  r - Research random topic")
                    print("  b - Find book about topic")
                    print("  s - Submit custom task")
                    print("  c - Check system status")
                    print("  q - Quit watch mode")
                
                else:
                    print(f"Unknown command: {cmd}")
                    
            except EOFError:
                break
            except Exception as e:
                self.messages.append(f"[ERROR] {e}")
    
    def inject_message(self, message: str):
        """Inject message from external source (like OpenClaw)"""
        self.messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] INJECTED: {message}")
        # Process injected message as task
        task = self.brain.submit(message)
        return task

def main():
    """Entry point"""
    watch = CortexLLMWatch()
    try:
        asyncio.run(watch.start())
    except KeyboardInterrupt:
        print("\n\nWatch stopped")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
