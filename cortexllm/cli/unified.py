#!/usr/bin/env python3
"""
CortexLLM Unified CLI
One interface for OpenCode, OpenClaw, Claude, and more
No flashing, simple REPL style
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime
import argparse

sys.path.insert(0, str(Path(__file__).parent.parent))
from cortexllm.utils.fancy import fancy, Colors

@dataclass
class Target:
    number: int
    name: str
    emoji: str
    status: str = "unknown"
    description: str = ""
    last_check: float = field(default_factory=lambda: 0)

class UnifiedCLI:
    def __init__(self):
        self.targets = {
            1: Target(1, "OpenCode", "💬", description="Ollama API"),
            2: Target(2, "OpenClaw", "🦀", description="Gateway"),
        }
        self.current_target = 1
        self.history: List[Dict] = []
        self.running = True
        self.messages = []
        
    async def start(self):
        """Start the unified CLI - no flashing"""
        self._show_banner()
        await self._initial_check()
        await self._repl()
    
    def _show_banner(self):
        """Show static banner once"""
        print(f"""
╔═══════════════════════════════════════════════════════════╗
║    🎯 CortexLLM Unified CLI                             ║
║    One interface for OpenCode and OpenClaw                ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    def _show_status(self):
        """Show current status of all targets (no clear screen)"""
        print(f"\n{Colors.BOLD}📡 Platform Status:{Colors.RESET}")
        
        for num, target in self.targets.items():
            status_icon = "🟢" if target.status == "online" else "🔴" if target.status == "offline" else "⚪"
            current = " ←" if num == self.current_target else ""
            print(f"   /{num} {target.emoji} {target.name:12} {status_icon} [{target.status.upper():8}]{current}")
        
        current = self.targets[self.current_target]
        print(f"\n{Colors.DIM}Current: {current.emoji} {current.name}{Colors.RESET}")
        
        if self.messages:
            print(f"\n{Colors.BOLD}📨 Last Message:{Colors.RESET}")
            last = self.messages[-1]
            print(f"   [{last['time'][11:19]}] {last['target']}: {last['message'][:60]}")
        print()
    
    async def _initial_check(self):
        """Initial platform check"""
        print(f"{Colors.DIM}Checking platforms...{Colors.RESET}")
        
        # Check OpenCode (Ollama)
        if await self._check_ollama():
            self.targets[1].status = "online"
            print(f"   ✅ OpenCode (Ollama) - Online")
        else:
            self.targets[1].status = "offline"
            print(f"   ❌ OpenCode (Ollama) - Offline (run: ollama serve)")
        
        # Check OpenClaw
        if await self._check_openclaw():
            self.targets[2].status = "online"
            print(f"   ✅ OpenClaw (Gateway) - Online")
        else:
            self.targets[2].status = "offline"
            print(f"   ❌ OpenClaw (Gateway) - Offline")
        
        print()
    
    async def _check_ollama(self) -> bool:
        try:
            import urllib.request
            req = urllib.request.Request('http://127.0.0.1:11434/api/tags', method='GET')
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except:
            return False
    
    async def _check_openclaw(self) -> bool:
        try:
            import urllib.request
            req = urllib.request.Request('http://127.0.0.1:18789/health', method='GET')
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except:
            return False
    
    async def _repl(self):
        """Main REPL - simple and clean"""
        while self.running:
            try:
                # Show prompt with current target
                current = self.targets[self.current_target]
                prompt = f"{current.emoji} [{current.name}]\n🎯 cortexllm> "
                
                user_input = input(prompt).strip()
                
                if not user_input:
                    continue
                
                await self._process_input(user_input)
                
            except EOFError:
                break
            except KeyboardInterrupt:
                print(f"\n\n{Colors.BOLD}👋 Goodbye!{Colors.RESET}")
                break
    
    async def _process_input(self, text: str):
        """Process user input"""
        if text.startswith('/'):
            await self._handle_command(text)
        else:
            await self._send_message(text)
    
    async def _handle_command(self, cmd: str):
        """Handle slash commands"""
        parts = cmd.split()
        command = parts[0].lower()
        
        # Switch targets /1, /2, /3, /4
        if command[1:].isdigit():
            target_num = int(command[1:])
            if target_num in self.targets:
                self.current_target = target_num
                target = self.targets[target_num]
                print(f"   ✅ Switched to {target.emoji} {target.name}")
                
                if target.status == "offline":
                    print(f"   ⚠️  Warning: {target.name} appears to be offline")
            else:
                print(f"   ❌ Unknown target {target_num}. Use /list to see targets.")
        
        elif command == '/list':
            self._show_status()
        
        elif command == '/status':
            await self._initial_check()
        
        elif command == '/history':
            self._show_history()
        
        elif command == '/help':
            self._show_help()
        
        elif command in ['/quit', '/q', '/exit']:
            self.running = False
            print(f"\n{Colors.BOLD}👋 Goodbye!{Colors.RESET}")
        
        else:
            print(f"   ❌ Unknown command: {command}")
            print(f"   Type /help for available commands")
    
    async def _send_message(self, message: str):
        """Send message to current target"""
        target = self.targets[self.current_target]
        
        if target.status == "offline":
            print(f"   ❌ Cannot send: {target.name} is offline")
            return
        
        print(f"   📤 Sending to {target.emoji} {target.name}...")
        
        if target.number == 1:
            success = await self._send_to_opencode(message)
        elif target.number == 2:
            success = await self._send_to_openclaw(message)
        else:
            success = False
        
        if success:
            print(f"   ✅ Message sent to {target.name}")
            self.messages.append({
                "time": datetime.now().isoformat(),
                "target": target.name,
                "message": message[:100]
            })
        else:
            print(f"   ❌ Failed to send to {target.name}")
    
    async def _send_to_opencode(self, message: str) -> bool:
        """Send via Ollama API"""
        try:
            import urllib.request
            payload = {
                "model": "llama3.2",
                "prompt": message,
                "stream": False
            }
            req = urllib.request.Request(
                'http://127.0.0.1:11434/api/generate',
                data=json.dumps(payload).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    # Could parse and display response here
                    return True
                return False
        except Exception as e:
            print(f"   Error: {e}")
            return False
    
    async def _send_to_openclaw(self, message: str) -> bool:
        """Send via OpenClaw Gateway"""
        try:
            import urllib.request
            payload = {"message": message}
            req = urllib.request.Request(
                'http://127.0.0.1:18789/message',
                data=json.dumps(payload).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"   Error: {e}")
            return False
    
    
    def _show_history(self):
        """Show message history"""
        if not self.messages:
            print(f"\n   No messages yet")
            return
        
        print(f"\n{Colors.BOLD}📨 Message History:{Colors.RESET}")
        for entry in self.messages[-10:]:
            time_str = entry['time'][11:19]
            print(f"   [{time_str}] {entry['target']}: {entry['message'][:50]}")
        print()
    
    def _show_help(self):
        """Show help"""
        print(f"""
{Colors.BOLD}CortexLLM Unified CLI Help{Colors.RESET}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{Colors.BOLD}Quick Switch:{Colors.RESET}
   /1          Switch to OpenCode (Ollama)
   /2          Switch to OpenClaw (Gateway)

{Colors.BOLD}Commands:{Colors.RESET}
   /list       Show platform status
   /status     Recheck platform connectivity
   /history    Show sent messages
   /help       Show this help
   /quit       Exit CLI

{Colors.BOLD}Sending Messages:{Colors.RESET}
   Just type your message and press Enter
   It will be sent to the current target

{Colors.BOLD}Tips:{Colors.RESET}
   • Check /status if messages aren't sending
   • Switch targets quickly with /1, /2, etc.
   • Ollama-only: No external API keys needed
""")

def main():
    parser = argparse.ArgumentParser(description="CortexLLM Unified CLI")
    parser.add_argument('--target', '-t', type=int, default=1,
                       help='Default target (1-4, default: 1)')
    
    args = parser.parse_args()
    
    cli = UnifiedCLI()
    cli.current_target = args.target
    
    try:
        asyncio.run(cli.start())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.BOLD}👋 Goodbye!{Colors.RESET}")

if __name__ == "__main__":
    main()
