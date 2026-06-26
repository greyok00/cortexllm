#!/usr/bin/env python3
"""
🎯 CortexLLM Watch - Unified monitoring for OpenCode & OpenClaw
Direct Ollama integration for cross-platform messaging
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import argparse
import subprocess

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cortexllm import Brain, Memory, Config
from cortexllm.utils.fancy import fancy, Colors

class PlatformConnector:
    """🔗 Connects to OpenCode and OpenClaw via Ollama"""
    
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434"):
        self.ollama_url = ollama_url
        self.platforms = {
            "opencode": {"status": "unknown", "last_ping": None},
            "openclaw": {"status": "unknown", "last_ping": None}
        }
    
    async def check_opencode(self) -> bool:
        """Check if OpenCode is running via Ollama"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_url}/api/tags", timeout=5) as resp:
                    if resp.status == 200:
                        self.platforms["opencode"]["status"] = "online"
                        self.platforms["opencode"]["last_ping"] = time.time()
                        return True
        except:
            pass
        self.platforms["opencode"]["status"] = "offline"
        return False
    
    async def check_openclaw(self) -> bool:
        """Check if OpenClaw gateway is running"""
        try:
            cfg = Config()
            port = cfg.get("gateway", "port", default=18789)
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
                    if resp.status == 200:
                        self.platforms["openclaw"]["status"] = "online"
                        self.platforms["openclaw"]["last_ping"] = time.time()
                        return True
        except:
            pass
        self.platforms["openclaw"]["status"] = "offline"
        return False
    
    async def send_to_opencode(self, message: str) -> bool:
        """Send message to OpenCode via Ollama"""
        try:
            import aiohttp
            payload = {
                "model": "llama3.2",
                "prompt": message,
                "stream": False
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=30
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            fancy.error(f"Failed to send to OpenCode: {e}")
            return False
    
    async def send_to_openclaw(self, message: str) -> bool:
        """Send message to OpenClaw gateway"""
        try:
            cfg = Config()
            port = cfg.get("gateway", "port", default=18789)
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://127.0.0.1:{port}/message",
                    json={"message": message},
                    timeout=10
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            fancy.error(f"Failed to send to OpenClaw: {e}")
            return False
    
    def get_status_board(self) -> Dict:
        """Get status of both platforms"""
        return self.platforms

class CortexWatch:
    """👁️ Main watch interface with fancy output"""
    
    def __init__(self):
        self.mem = Memory()
        self.cfg = Config()
        self.brain = Brain(self.cfg, self.mem)
        self.connector = PlatformConnector()
        self.running = True
        self.messages: List[Dict] = []
        self.current_platform = "auto"  # auto, opencode, openclaw, both
        
    async def start(self):
        """🚀 Start the watch interface"""
        self._show_welcome()
        
        # Initialize brain
        await self.brain.start()
        
        # Start monitoring
        await asyncio.gather(
            self._platform_monitor_loop(),
            self._ui_loop(),
            self._input_loop()
        )
    
    def _show_welcome(self):
        """🎉 Show welcome screen"""
        fancy.clear()
        fancy.header("CortexLLM Unified Watch", "🎯")
        
        fancy.print(fancy.box("""
🧠 Brain Status: Initializing...
🔗 Ollama URL: http://127.0.0.1:11434
📡 OpenCode: Checking...
📡 OpenClaw: Checking...

✨ Ready to synchronize across platforms!
        """, emoji="🚀"))
        
        fancy.print("\n" + fancy._color("Commands:", Colors.CYAN + Colors.BOLD))
        fancy.list_items([
            "send [message] - Send to active platform(s)",
            "switch [opencode|openclaw|both] - Change target",
            "status - Show platform status",
            "task [description] - Submit task to brain",
            "quit/exit - Stop watching"
        ], emoji="→")
        fancy.print()
    
    async def _platform_monitor_loop(self):
        """📡 Monitor platform connectivity"""
        while self.running:
            await self.connector.check_opencode()
            await self.connector.check_openclaw()
            await asyncio.sleep(10)  # Check every 10 seconds
    
    async def _ui_loop(self):
        """🖥️ Update the fancy UI"""
        while self.running:
            self._render_dashboard()
            await asyncio.sleep(1)
    
    def _render_dashboard(self):
        """📊 Render the main dashboard"""
        fancy.clear()
        
        # Header
        fancy.header(f"CortexLLM Watch - {datetime.now().strftime('%H:%M:%S')}", "🎯")
        
        # Platform status
        platforms = self.connector.get_status_board()
        status_rows = []
        for name, data in platforms.items():
            status = "🟢" if data["status"] == "online" else "🔴"
            last_ping = "Never" if not data["last_ping"] else f"{int(time.time() - data['last_ping'])}s ago"
            status_rows.append([status, name.upper(), data["status"], last_ping])
        
        fancy.print(fancy.table(
            ["", "Platform", "Status", "Last Ping"],
            status_rows,
            "Platform Connectivity"
        ))
        
        # Brain status
        brain_status = self.brain.status()
        fancy.print(fancy.status_card(
            "Brain",
            "running" if brain_status["running"] else "stopped",
            {
                "Tasks": brain_status["tasks"],
                "Workers": brain_status["workers"],
                "Mode": getattr(self.brain, 'mode', 'auto')
            }
        ))
        
        # Recent messages
        if self.messages:
            fancy.print(f"\n{ fancy._color('📨 Recent Messages:', Colors.CYAN + Colors.BOLD)}")
            for msg in self.messages[-5:]:
                platform = msg.get('platform', 'unknown')
                content = msg.get('content', '')[:50]
                time_str = datetime.fromtimestamp(msg.get('time', 0)).strftime('%H:%M:%S')
                fancy.print(f"  {fancy._color('├─', Colors.DIM)} [{time_str}] {platform}: {content}")
        
        # Command prompt hint
        fancy.print(f"\n{ fancy._color('💡 Type command or message (send [opencode|openclaw|both] [message])', Colors.DIM)}")
    
    async def _input_loop(self):
        ""️ Handle user input"""
        while self.running:
            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, "\n🎯 cortexllm> "
                )
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                
                await self._process_command(user_input)
                
            except EOFError:
                break
            except KeyboardInterrupt:
                self.running = False
                break
    
    async def _process_command(self, cmd: str):
        ""️ Process user commands"""
        parts = cmd.split(maxsplit=2)
        action = parts[0].lower()
        
        if action in ["quit", "exit", "q"]:
            self.running = False
            fancy.print(fancy.success("Shutting down..."))
            await self.brain.stop()
        
        elif action == "send":
            if len(parts) < 3:
                fancy.error("Usage: send [opencode|openclaw|both] [message]")
                return
            
            target = parts[1]
            message = parts[2]
            
            await self._send_message(target, message)
        
        elif action == "switch":
            if len(parts) < 2:
                fancy.error("Usage: switch [opencode|openclaw|both|auto]")
                return
            
            self.current_platform = parts[1]
            fancy.success(f"Switched to {parts[1]}")
        
        elif action == "status":
            self._render_dashboard()
        
        elif action == "task":
            if len(parts) < 2:
                fancy.error("Usage: task [description]")
                return
            
            description = parts[1]
            task = self.brain.submit(description)
            fancy.success(f"Task submitted: {task.id}")
            self.messages.append({
                "platform": "brain",
                "content": f"Task: {description}",
                "time": time.time()
            })
        
        elif action == "help":
            self._show_help()
        
        else:
            # Treat as direct message to current platform
            await self._send_message(self.current_platform, cmd)
    
    async def _send_message(self, target: str, message: str):
        ""📨 Send message to specified platform(s)"""
        fancy.print(f"📤 Sending to {target}...")
        
        success = []
        
        if target in ["opencode", "both"]:
            if await self.connector.send_to_opencode(message):
                success.append("OpenCode")
                self.messages.append({
                    "platform": "opencode",
                    "content": message,
                    "time": time.time()
                })
        
        if target in ["openclaw", "both"]:
            if await self.connector.send_to_openclaw(message):
                success.append("OpenClaw")
                self.messages.append({
                    "platform": "openclaw",
                    "content": message,
                    "time": time.time()
                })
        
        if success:
            fancy.success(f"Sent to: {', '.join(success)}")
        else:
            fancy.error("Failed to send to any platform")
    
    def _show_help(self):
        ""❓ Show help information"""
        fancy.print(fancy.box("""
COMMANDS:
  send [platform] [message]   Send message to platform
    platforms: opencode, openclaw, both
    
  switch [platform]          Change default target
    platforms: opencode, openclaw, both, auto
    
  task [description]         Submit task to brain
  
  status                     Show platform status
  
  help                       Show this help
  
  quit/exit                  Stop watching

EXAMPLES:
  send opencode "Hello from CortexLLM!"
  send both "Broadcast message"
  switch opencode
  task "Research Python async patterns"
        """, emoji="📖"))

def main():
    ""🚀 Entry point"""
    parser = argparse.ArgumentParser(
        description="🎯 CortexLLM Watch - Unified monitoring for OpenCode & OpenClaw"
    )
    parser.add_argument(
        "--ollama-url",
        default="http://127.0.0.1:11434",
        help="Ollama API URL (default: http://127.0.0.1:11434)"
    )
    parser.add_argument(
        "--platform",
        choices=["opencode", "openclaw", "both", "auto"],
        default="auto",
        help="Default target platform"
    )
    
    args = parser.parse_args()
    
    watch = CortexWatch()
    watch.connector.ollama_url = args.ollama_url
    watch.current_platform = args.platform
    
    try:
        asyncio.run(watch.start())
    except KeyboardInterrupt:
        fancy.print(f"\n{fancy.success('Goodbye! 👋')}")
    except Exception as e:
        fancy.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
