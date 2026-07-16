#!/usr/bin/env python3
"""
CortexLLM Anti-Hallucination Protocol

MUST run BEFORE any code generation or tool execution.

Verifies:
1. CLI commands - flags, syntax, help docs
2. Service health - is it actually running?
3. File paths - do they exist?
4. User claims - verify what user said matches reality
5. Web search - if uncertain, search before answering

Usage:
    from anti_hallucination import verify_before_code

    # Call before generating any code
    verification = verify_before_code(
        user_prompt="Fix the gateway config",
        context={"files_mentioned": ["~/.openclaw/gateway.json"]}
    )

    if not verification.passed:
        print("BLOCKED: " + verification.blocker)
        return

    # Safe to proceed with code generation
"""

import json
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Paths to verify
COMMON_PATHS = {
    "gateway": Path.home() / ".openclaw/openclaw.json",
    "cortexllm_config": Path.home() / ".config/cortexllm/config.json",
    "openclaw_sessions": Path.home() / ".openclaw/agents/brain/sessions",
    "memory_hot": Path.home() / ".config/cortexllm/memory/hot",
    "memory_warm": Path.home() / ".config/cortexllm/memory/warm",
}

# Services to check
SERVICES = {
    "ollama": {"port": 11434, "process": "ollama"},
    "openclaw_gateway": {"port": 18789, "process": "gateway"},
    "searxng": {"port": 8888, "process": "searxng"},
    "browser_cdp": {"port": 9222, "process": "brave|chrome"},
}


class VerificationResult:
    def __init__(self):
        self.passed = True
        self.blocker: Optional[str] = None
        self.verifications: List[Dict] = []
        self.warnings: List[str] = []
        self.recommendations: List[str] = []
        self.web_search_needed = False
        self.web_search_query: Optional[str] = None

    def add_verification(self, name: str, passed: bool, details: str):
        self.verifications.append({
            "name": name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        })
        if not passed:
            self.passed = False
            if not self.blocker:
                self.blocker = f"{name} verification failed: {details}"

    def add_warning(self, msg: str):
        self.warnings.append(msg)

    def add_recommendation(self, msg: str):
        self.recommendations.append(msg)

    def to_dict(self) -> Dict:
        return {
            "passed": self.passed,
            "blocker": self.blocker,
            "verifications": self.verifications,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "web_search_needed": self.web_search_needed,
            "web_search_query": self.web_search_query,
        }


def verify_cli_command(command: str) -> VerificationResult:
    """
    Verify a CLI command before execution.

    Checks:
    - Command exists (which/where)
    - Flags are valid (--help parsing)
    - Arguments make sense
    """
    result = VerificationResult()

    # Extract base command
    parts = command.split()
    if not parts:
        result.add_verification("CLI", False, "Empty command")
        return result

    base_cmd = parts[0]

    # Check if command exists
    try:
        which_result = subprocess.run(
            ["which", base_cmd],
            capture_output=True,
            text=True,
            timeout=5
        )
        if which_result.returncode != 0:
            result.add_verification("CLI command exists", False, f"'{base_cmd}' not found in PATH")
            result.add_recommendation(f"Install {base_cmd} or check PATH")
            return result
        result.add_verification("CLI command exists", True, f"Found at: {which_result.stdout.strip()}")
    except Exception as e:
        result.add_verification("CLI command exists", False, f"Error checking: {e}")
        return result

    # Check --help for flag validation
    try:
        help_result = subprocess.run(
            [base_cmd, "--help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        help_text = help_result.stdout + help_result.stderr

        # Verify flags mentioned in command exist
        for part in parts[1:]:
            if part.startswith("-"):
                # Extract flag name (handle --flag=value and --flag value)
                flag = part.split("=")[0].lstrip("-")
                if flag and flag not in help_text.lower():
                    result.add_warning(f"Flag '-{flag}' may not exist for {base_cmd}")
                    result.web_search_needed = True
                    result.web_search_query = f"{base_cmd} command line flags reference"

        result.add_verification("CLI flags valid", True, "Flags appear valid")

    except subprocess.TimeoutExpired:
        result.add_warning(f"--help timed out for {base_cmd}")
    except Exception as e:
        result.add_warning(f"Could not verify flags: {e}")

    return result


def verify_browser_cdp() -> VerificationResult:
    """
    Verify browser CDP is accessible and can read pages.
    This is a special check because agents often hallucinate browser access issues.
    """
    result = VerificationResult()

    # Check port 9222 is listening
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        conn = sock.connect_ex(('127.0.0.1', 9222))
        sock.close()
        if conn != 0:
            result.add_verification("Browser CDP port", False, "Port 9222 not listening")
            result.add_recommendation("Restart Brave with --remote-debugging-port=9222")
            return result
        result.add_verification("Browser CDP port", True, "Port 9222 is listening")
    except Exception as e:
        result.add_verification("Browser CDP port", False, f"Error: {e}")
        return result

    # Check CDP version endpoint
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=3) as resp:
            data = json.loads(resp.read())
            result.add_verification("CDP version endpoint", True, f"Browser: {data.get('Browser', 'unknown')}")
    except Exception as e:
        result.add_verification("CDP version endpoint", False, f"Cannot reach: {e}")
        result.add_recommendation("Check Brave is running with --remote-allow-origins=*")
        return result

    # Check tabs are accessible
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=3) as resp:
            tabs = json.loads(resp.read())
            if len(tabs) == 0:
                result.add_verification("CDP tabs accessible", False, "No tabs found")
                result.add_recommendation("Open a browser window first")
                return result
            result.add_verification("CDP tabs accessible", True, f"{len(tabs)} tabs accessible")
    except Exception as e:
        result.add_verification("CDP tabs accessible", False, f"Cannot list tabs: {e}")
        result.add_recommendation("Browser may need --remote-allow-origins=* flag")
        return result

    return result


def verify_service_running(service_name: str) -> VerificationResult:
    """
    Verify a service is actually running before trying to use it.
    """
    result = VerificationResult()

    if service_name not in SERVICES:
        result.add_verification(f"Service {service_name}", False, "Unknown service")
        return result

    config = SERVICES[service_name]

    # Check port
    try:
        netstat = subprocess.run(
            ["netstat", "-tlnp"],
            capture_output=True,
            text=True,
            timeout=5
        )
        port_listening = f":{config['port']}" in netstat.stdout

        if not port_listening:
            result.add_verification(
                f"Service {service_name} port",
                False,
                f"Port {config['port']} not listening"
            )
            result.add_recommendation(f"Start {service_name} service")
        else:
            result.add_verification(
                f"Service {service_name} port",
                True,
                f"Port {config['port']} is listening"
            )
    except Exception as e:
        result.add_verification(f"Service {service_name} port", False, f"Error checking port: {e}")

    # Check process
    try:
        pgrep = subprocess.run(
            ["pgrep", "-f", config["process"]],
            capture_output=True,
            timeout=5
        )
        if pgrep.returncode != 0:
            result.add_warning(f"Process '{config['process']}' not found")
        else:
            result.add_verification(
                f"Service {service_name} process",
                True,
                f"PID: {pgrep.stdout.strip()}"
            )
    except Exception as e:
        result.add_warning(f"Could not check process: {e}")

    return result


def verify_file_exists(path: str, must_be_readable: bool = True) -> VerificationResult:
    """
    Verify a file path exists and is accessible.
    """
    result = VerificationResult()

    # Expand home directory
    expanded = Path(path).expanduser()

    if not expanded.exists():
        result.add_verification(
            f"File exists: {path}",
            False,
            f"Path does not exist: {expanded}"
        )
        result.add_recommendation("Check file path or create the file")
        return result

    result.add_verification(
        f"File exists: {path}",
        True,
        f"Found at: {expanded}"
    )

    if must_be_readable:
        try:
            expanded.read_text()
            result.add_verification(
                f"File readable: {path}",
                True,
                "File is readable"
            )
        except PermissionError:
            result.add_verification(
                f"File readable: {path}",
                False,
                "Permission denied"
            )
        except Exception as e:
            result.add_verification(
                f"File readable: {path}",
                False,
                f"Error: {e}"
            )

    return result


def verify_user_claim(claim: str, context: Dict) -> VerificationResult:
    """
    Verify a user's claim against actual system state.

    Examples:
    - User: "The gateway is broken" → Check if gateway is actually running
    - User: "I already have a config file" → Check if file exists
    - User: "This worked yesterday" → Search for what changed
    """
    result = VerificationResult()

    claim_lower = claim.lower()

    # Check for claims about services
    for service_name in SERVICES:
        if service_name in claim_lower or "gateway" in claim_lower:
            service_result = verify_service_running(service_name)
            result.verifications.extend(service_result.verifications)
            result.warnings.extend(service_result.warnings)

            # If service is running but user says broken, might be config issue
            if service_result.passed and ("broken" in claim_lower or "not working" in claim_lower):
                result.add_warning("Service is running but user reports issues - may be config problem")
                result.recommendations.append("Check configuration files and logs")

    # Check for claims about files
    file_pattern = r'(?:file|config|path)[\s:]+["\']?([~/.\w\-/]+)["\']?'
    matches = re.findall(file_pattern, claim, re.IGNORECASE)
    for path in matches:
        file_result = verify_file_exists(path)
        result.verifications.extend(file_result.verifications)
        result.warnings.extend(file_result.warnings)

    # Check for uncertainty - may need web search
    uncertainty_words = ["think", "maybe", "probably", "not sure", "i guess", "seems like"]
    if any(word in claim_lower for word in uncertainty_words):
        result.web_search_needed = True
        result.web_search_query = claim

    return result


def verify_before_code(user_prompt: str, context: Optional[Dict] = None) -> VerificationResult:
    """
    MAIN ENTRY POINT - Call before generating any code.

    Performs all verification checks:
    1. Extract and verify CLI commands
    2. Check mentioned services are running
    3. Verify file paths exist
    4. Validate user claims
    5. Determine if web search is needed

    Returns VerificationResult with:
    - passed: True if safe to proceed with code generation
    - blocker: Reason if blocked
    - verifications: List of all checks performed
    - recommendations: What to do before proceeding
    """
    result = VerificationResult()
    context = context or {}

    prompt_lower = user_prompt.lower()

    # 1. Extract potential CLI commands from prompt
    # Look for patterns like "run X", "execute X", "X command"
    cmd_patterns = [
        r'(?:run|execute|call|invoke)\s+(\w+)',
        r'(\w+)\s+(?:command|script|tool)',
        r'(?:use|try)\s+(\w+)',
    ]
    for pattern in cmd_patterns:
        matches = re.findall(pattern, prompt_lower)
        for cmd in matches:
            if cmd not in ["the", "a", "an", "this", "that"]:
                cmd_result = verify_cli_command(cmd)
                result.verifications.extend(cmd_result.verifications)
                result.warnings.extend(cmd_result.warnings)
                if not cmd_result.passed:
                    result.blocker = f"CLI verification failed: {cmd}"

    # 2. Check browser CDP specifically (common hallucination source)
    browser_keywords = ["browser", "canvas", "webpage", "tab", "cdp", "navigate", "click", "fetch page"]
    if any(kw in prompt_lower for kw in browser_keywords):
        browser_result = verify_browser_cdp()
        result.verifications.extend(browser_result.verifications)
        result.warnings.extend(browser_result.warnings)
        if not browser_result.passed:
            result.blocker = "Browser CDP verification failed - agent may hallucinate access issues"
            for rec in browser_result.recommendations:
                result.add_recommendation(rec)

    # Check other services mentioned
    for service_name in SERVICES:
        if service_name in prompt_lower:
            service_result = verify_service_running(service_name)
            result.verifications.extend(service_result.verifications)
            result.warnings.extend(service_result.warnings)
            if not service_result.passed:
                result.add_recommendation(f"Start {service_name} before proceeding")

    # 3. Verify file paths mentioned
    paths_to_check = context.get("files_mentioned", [])
    for path in paths_to_check:
        file_result = verify_file_exists(path)
        result.verifications.extend(file_result.verifications)
        result.warnings.extend(file_result.warnings)

    # 4. Verify user claims
    if "claim" in context:
        claim_result = verify_user_claim(context["claim"], context)
        result.verifications.extend(claim_result.verifications)
        result.warnings.extend(claim_result.warnings)

    # 5. Determine if web search needed
    # If prompt mentions uncertainty or unfamiliar tool
    if result.web_search_needed:
        result.add_recommendation(f"Web search recommended: {result.web_search_query}")

    # Final pass/fail
    if not result.passed:
        result.blocker = "Verification failed - address issues before code generation"

    return result


def format_verification_report(result: VerificationResult) -> str:
    """Format verification result for display to user."""
    lines = []

    if result.passed:
        lines.append("✅ Anti-Hallucination Check: PASSED")
    else:
        lines.append("❌ Anti-Hallucination Check: BLOCKED")
        if result.blocker:
            lines.append(f"   Blocker: {result.blocker}")

    lines.append("")
    lines.append("Verifications:")
    for v in result.verifications:
        icon = "✓" if v["passed"] else "✗"
        lines.append(f"  {icon} {v['name']}: {v['details']}")

    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in result.warnings:
            lines.append(f"  ⚠ {w}")

    if result.recommendations:
        lines.append("")
        lines.append("Recommendations:")
        for r in result.recommendations:
            lines.append(f"  → {r}")

    if result.web_search_needed:
        lines.append("")
        lines.append(f"🔍 Web search recommended: {result.web_search_query}")

    return "\n".join(lines)


# CLI test
if __name__ == "__main__":
    print("=== CortexLLM Anti-Hallucination Protocol ===\n")

    test_prompts = [
        "Run ollama list to check models",
        "Fix the gateway config at ~/.openclaw/openclaw.json",
        "The searxng service is broken",
        "Execute python3 --version",
        "Navigate to Canvas and get my grades",
    ]

    for prompt in test_prompts:
        print(f"\n--- Testing: '{prompt}' ---\n")
        result = verify_before_code(prompt)
        print(format_verification_report(result))
        print()
