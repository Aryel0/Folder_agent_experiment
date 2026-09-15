# 🌍 SandboxWorld: Hardened Docker Sandbox & Simulated World Engine for AI Agents

**SandboxWorld** is a standalone, security-hardened Docker sandbox and simulated world exploration framework designed for autonomous AI agents.

It turns an isolated Docker container into an interactive virtual computer ("simulated world") where agents can safely execute arbitrary commands, explore directories, solve quests, debug code, and inspect systems—all while strictly protecting the host machine from privilege escalation, container escapes, or unauthorized network access.

---

## 🔒 Security Architecture

SandboxWorld enforces mandatory enterprise-grade security barriers:

```
Host Operating System
 │
 └── Docker Engine (WSL2 / Linux / Docker Desktop)
      │
      └── Isolated Container ("Simulated World")
           ├── User: agent (UID: 1000, GID: 1000) [NON-ROOT]
           ├── Root Filesystem: / [READ-ONLY]
           ├── Writable Workspace: /workspace (Strictly bound)
           ├── In-Memory Tempfs: /tmp (rw, noexec, nosuid, size=64m)
           ├── In-Memory Home: /home/agent (rw, nosuid, size=64m)
           ├── Linux Capabilities: --cap-drop=ALL
           ├── Privilege Escalation: --security-opt no-new-privileges:true
           ├── Syscall Filter: Strict Seccomp Profile (blocks mount, ptrace, reboot, etc.)
           ├── Network Isolation: --network none (air-gapped by default)
           └── Resource Limits: 1.0 CPU, 512MB RAM, 64 PIDs (Anti-Fork-Bomb)
```

### Prohibited & Hard-Blocked Settings:
- ❌ **NO `--privileged`** (Rejected with `SecurityViolationError`)
- ❌ **NO root execution** (`user="0"` or `"root"` rejected)
- ❌ **NO Docker socket mounts** (`/var/run/docker.sock` explicitly blocked)
- ❌ **NO host root mounting** (`/`, `C:\`, `C:\Windows` explicitly blocked)
- ❌ **NO host network** (`--network host` explicitly blocked)

---

## 🚀 Quickstart

### 1. Installation
Install SandboxWorld in your Python environment:
```bash
pip install -e ./sandbox_world
```

### 2. Build the Hardened Sandbox Image
```bash
sandbox-world build
```

### 3. Command-Line Interface (CLI)
```bash
# Check Docker and container status
sandbox-world status

# Start or reset the container to clean state
sandbox-world reset

# Run shell commands in the sandbox
sandbox-world exec "whoami"
sandbox-world exec "ls -la /workspace"

# Run Python scripts safely
sandbox-world py "import os; print('UID:', os.getuid())"

# Run simulated world exploration scenarios & view the live HUD
sandbox-world eval --scenario broken_pipeline --dry-run
```

---

## 🐍 Python API for AI Agents

Any AI agent framework (LangChain, AutoGen, LlamaIndex, custom agents) can integrate SandboxWorld in a few lines of code:

```python
from sandbox_world import DockerSandbox, WorldObserver

# Initialize sandbox with default hardened security
sandbox = DockerSandbox()

# Execute shell command as non-root 'agent'
result = sandbox.execute_command("whoami")
print(result.stdout)  # "agent"

# Execute Python snippet
py_result = sandbox.execute_python("print(2 ** 10)")
print(py_result.stdout)  # "1024"
```

### Observing World Changes & Exploration Behavior:
```python
from sandbox_world import WorldObserver

observer = WorldObserver("/workspace")

# Record an action taken by the agent
observer.record_action(
    action_type="bash",
    command="python3 fix_script.py",
    output="Script fixed.",
    duration=0.2
)

# Inspect world mutations
delta = observer.total_world_delta()
print("Files Created:", delta.created)
print("Files Modified:", delta.modified)

# View exploration vitals (detects loops, thrashing, efficiency)
metrics = observer.get_exploration_metrics()
print("Exploration Efficiency:", metrics["exploration_efficiency_pct"], "%")
print("Loop Count:", metrics["loop_count"])
```

---

## 🏆 Simulated World Scenarios (Quests)

SandboxWorld includes pre-built scenarios to test and benchmark agent exploration:

| Scenario | Objective |
| :--- | :--- |
| **`broken_pipeline`** | Diagnose a crashing telemetry pipeline in `/workspace`, fix the bug, and output `clean_summary.json`. |
| **`system_audit`** | Audit server configuration files to find, extract, and decode a hidden backup key into `decoded_key.txt`. |
| **`incident_response`** | Investigate web server access logs to detect SQL injection / path traversal attacker IP and output `incident_report.json`. |

### Creating Custom Scenarios:
```python
from sandbox_world import WorldScenario, ScenarioResult, WorldObserver
from pathlib import Path

class CustomQuest(WorldScenario):
    name = "custom_quest"
    description = "A custom exploration scenario."
    briefing = "Find the hidden clue in /workspace and write your answer to output.txt."

    def setup(self, workspace_dir: str):
        (Path(workspace_dir) / "clue.txt").write_text("The secret code is 42.")

    def verify(self, workspace_dir: str, agent_output: str, observer: WorldObserver) -> ScenarioResult:
        output_file = Path(workspace_dir) / "output.txt"
        success = output_file.exists() and "42" in output_file.read_text()
        return ScenarioResult(
            scenario_name=self.name,
            success=success,
            score=100.0 if success else 0.0,
            objectives_met=["Output created with answer"] if success else [],
            objectives_failed=[] if success else ["Failed to generate output.txt with 42"]
        )
```

---

## 🧪 Testing

Run the self-contained test suite:
```bash
python -m unittest discover sandbox_world/tests/
```

---

## 📄 License
MIT License. Free for research, personal, and commercial agent development.
