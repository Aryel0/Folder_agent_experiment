from __future__ import annotations
import os
import json
import base64
import shutil
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
from sandbox_world.observer import WorldObserver

logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """Outcome of an agent's attempt on a simulated world scenario."""
    scenario_name: str
    success: bool
    score: float  # 0.0 to 100.0
    objectives_met: List[str] = field(default_factory=list)
    objectives_failed: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    feedback: str = ""

    def summary(self) -> str:
        status = "PASSED" if self.success else "FAILED"
        total = len(self.objectives_met) + len(self.objectives_failed)
        return f"[{status}] {self.scenario_name}: Score {self.score:.1f}% ({len(self.objectives_met)}/{total} objectives met)"


class WorldScenario(ABC):
    """Abstract base class for a simulated world scenario / quest."""

    name: str = ""
    description: str = ""
    briefing: str = ""

    @abstractmethod
    def setup(self, workspace_dir: str) -> None:
        """Seed the workspace with mock files, broken systems, or clues."""
        ...

    @abstractmethod
    def verify(
        self,
        workspace_dir: str,
        agent_output: str,
        observer: WorldObserver
    ) -> ScenarioResult:
        """Inspect the final state of the simulated world and grade the outcome."""
        ...


class BrokenPipelineScenario(WorldScenario):
    """Scenario: Agent must diagnose and fix a crashing data pipeline in /workspace."""

    name = "broken_pipeline"
    description = "Repair a crashed telemetry pipeline script and generate clean summary JSON."
    briefing = (
        "A critical telemetry pipeline at '/workspace/data_pipeline.py' is failing. "
        "Explore the workspace, diagnose why it is crashing, fix the code, and execute it "
        "so that it generates a valid '/workspace/clean_summary.json' file containing aggregated totals."
    )

    def setup(self, workspace_dir: str) -> None:
        ws = Path(workspace_dir)
        ws.mkdir(parents=True, exist_ok=True)

        csv_content = (
            "timestamp,server_id,cpu_pct,memory_mb\n"
            "2026-09-12 10:00,srv-1,45.2,512\n"
            "2026-09-12 10:01,srv-2,N/A,1024\n"
            "2026-09-12 10:02,srv-1,78.5,512\n"
            "2026-09-12 10:03,srv-3,62.1,2048\n"
            "2026-09-12 10:04,srv-2,89.9,1024\n"
        )
        (ws / "raw_telemetry.csv").write_text(csv_content, encoding="utf-8")

        script_content = '''import csv
import json

def process():
    total_cpu = 0.0
    count = 0
    with open("raw_telemetry.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_cpu += float(row["cpu_pct"])
            count += 1
            
    avg_cpu = total_cpu / count
    summary = {
        "status": "OK",
        "processed_records": count,
        "average_cpu": round(avg_cpu, 2)
    }
    with open("clean_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("Pipeline finished successfully!")

if __name__ == "__main__":
    process()
'''
        (ws / "data_pipeline.py").write_text(script_content, encoding="utf-8")

    def verify(
        self,
        workspace_dir: str,
        agent_output: str,
        observer: WorldObserver
    ) -> ScenarioResult:
        ws = Path(workspace_dir)
        summary_path = ws / "clean_summary.json"
        met = []
        failed = []

        if summary_path.exists():
            met.append("clean_summary.json was generated")
            try:
                data = json.loads(summary_path.read_text(encoding="utf-8"))
                if "average_cpu" in data and isinstance(data["average_cpu"], (int, float)):
                    met.append("clean_summary.json contains valid average_cpu metric")
                else:
                    failed.append("clean_summary.json missing valid 'average_cpu' field")
            except Exception as e:
                failed.append(f"clean_summary.json is not valid JSON: {e}")
        else:
            failed.append("clean_summary.json was not created")

        delta = observer.total_world_delta()
        if "data_pipeline.py" in delta.modified:
            met.append("data_pipeline.py was repaired")
        else:
            failed.append("data_pipeline.py was not modified")

        total_objs = len(met) + len(failed)
        score = (len(met) / total_objs * 100.0) if total_objs > 0 else 0.0
        success = (len(failed) == 0)

        return ScenarioResult(
            scenario_name=self.name,
            success=success,
            score=score,
            objectives_met=met,
            objectives_failed=failed,
            metrics=observer.get_exploration_metrics(),
            feedback="Pipeline repaired and output generated." if success else "Pipeline repair incomplete."
        )


class SystemAuditScenario(WorldScenario):
    """Scenario: Agent must find an encoded secret key buried in configuration files."""

    name = "system_audit"
    description = "Audit directory structure to discover and decode a hidden backup key."
    briefing = (
        "You are auditing a virtual server at '/workspace'. "
        "Find the base64-encoded backup authorization key hidden within the configuration files, "
        "decode it, and write the plaintext key into '/workspace/decoded_key.txt'."
    )

    SECRET_PLAIN = "UplinkSecret2026"

    def setup(self, workspace_dir: str) -> None:
        ws = Path(workspace_dir)
        cfg_dir = ws / "config" / "services"
        cfg_dir.mkdir(parents=True, exist_ok=True)

        encoded = base64.b64encode(self.SECRET_PLAIN.encode()).decode()
        env_content = (
            "# System Environment Configurations\n"
            "SERVICE_NAME=telemetry_daemon\n"
            "PORT=8080\n"
            f"AUTH_BACKUP_KEY_B64={encoded}\n"
            "LOG_LEVEL=INFO\n"
        )
        (cfg_dir / "backup.env").write_text(env_content, encoding="utf-8")

        (ws / "README.txt").write_text("Standard workstation directory.", encoding="utf-8")
        (ws / "config" / "general.json").write_text('{"environment": "staging"}', encoding="utf-8")

    def verify(
        self,
        workspace_dir: str,
        agent_output: str,
        observer: WorldObserver
    ) -> ScenarioResult:
        ws = Path(workspace_dir)
        key_file = ws / "decoded_key.txt"
        met = []
        failed = []

        if key_file.exists():
            met.append("decoded_key.txt created")
            content = key_file.read_text(encoding="utf-8").strip()
            if self.SECRET_PLAIN in content:
                met.append("decoded_key.txt contains the correct plaintext secret")
            else:
                failed.append(f"decoded_key.txt content '{content[:30]}' does not match expected secret")
        else:
            if self.SECRET_PLAIN in agent_output:
                met.append("Decoded secret correctly identified in agent response")
            else:
                failed.append("decoded_key.txt not created and secret not found in output")

        total_objs = len(met) + len(failed)
        score = (len(met) / total_objs * 100.0) if total_objs > 0 else 0.0
        success = (len(failed) == 0)

        return ScenarioResult(
            scenario_name=self.name,
            success=success,
            score=score,
            objectives_met=met,
            objectives_failed=failed,
            metrics=observer.get_exploration_metrics(),
            feedback="Secret discovered and decoded." if success else "Secret not found or improperly decoded."
        )


class IncidentResponseScenario(WorldScenario):
    """Scenario: Agent must investigate web server logs and identify malicious IP traffic."""

    name = "incident_response"
    description = "Investigate access logs to detect SQL injection / path traversal attacker IP."
    briefing = (
        "Suspicious requests were logged on the virtual server at '/workspace/server/access.log'. "
        "Explore the logs, find the malicious attacker's IP address and attack type, "
        "and generate an incident report at '/workspace/incident_report.json' with keys "
        "'attacker_ip' and 'attack_type'."
    )

    ATTACKER_IP = "198.51.100.42"

    def setup(self, workspace_dir: str) -> None:
        ws = Path(workspace_dir)
        server_dir = ws / "server"
        server_dir.mkdir(parents=True, exist_ok=True)

        log_lines = [
            '192.168.1.10 - - [12/Sep/2026:12:01:05 +0000] "GET /index.html HTTP/1.1" 200 1024',
            '192.168.1.15 - - [12/Sep/2026:12:02:10 +0000] "GET /static/style.css HTTP/1.1" 200 4021',
            f'{self.ATTACKER_IP} - - [12/Sep/2026:12:03:00 +0000] "GET /login?user=admin\'%20OR%201=1-- HTTP/1.1" 401 512',
            f'{self.ATTACKER_IP} - - [12/Sep/2026:12:03:15 +0000] "GET /../../../../etc/passwd HTTP/1.1" 403 210',
            '192.168.1.20 - - [12/Sep/2026:12:04:00 +0000] "GET /api/status HTTP/1.1" 200 128',
            f'{self.ATTACKER_IP} - - [12/Sep/2026:12:04:30 +0000] "POST /api/exec?cmd=id HTTP/1.1" 403 180',
        ]
        (server_dir / "access.log").write_text("\n".join(log_lines), encoding="utf-8")

    def verify(
        self,
        workspace_dir: str,
        agent_output: str,
        observer: WorldObserver
    ) -> ScenarioResult:
        ws = Path(workspace_dir)
        report_path = ws / "incident_report.json"
        met = []
        failed = []

        if report_path.exists():
            met.append("incident_report.json was created")
            try:
                data = json.loads(report_path.read_text(encoding="utf-8"))
                if str(data.get("attacker_ip", "")).strip() == self.ATTACKER_IP:
                    met.append("Attacker IP correctly identified")
                else:
                    failed.append(f"Attacker IP mismatch: expected {self.ATTACKER_IP}, got {data.get('attacker_ip')}")

                if "attack_type" in data and any(term in str(data["attack_type"]).lower() for term in ["sql", "traversal", "injection"]):
                    met.append("Attack type correctly categorized")
                else:
                    failed.append("Attack type missing or inaccurate")
            except Exception as e:
                failed.append(f"Failed to parse incident_report.json: {e}")
        else:
            if self.ATTACKER_IP in agent_output:
                met.append("Attacker IP identified in output")
            else:
                failed.append("incident_report.json missing and attacker IP not identified")

        total_objs = len(met) + len(failed)
        score = (len(met) / total_objs * 100.0) if total_objs > 0 else 0.0
        success = (len(failed) == 0)

        return ScenarioResult(
            scenario_name=self.name,
            success=success,
            score=score,
            objectives_met=met,
            objectives_failed=failed,
            metrics=observer.get_exploration_metrics(),
            feedback="Incident analyzed and reported." if success else "Malicious activity not fully resolved."
        )


class ScenarioManager:
    """Manages discovery and execution of simulated world scenarios."""

    def __init__(self):
        self.scenarios: Dict[str, WorldScenario] = {}
        self._register_defaults()

    def _register_defaults(self):
        for cls in [BrokenPipelineScenario, SystemAuditScenario, IncidentResponseScenario]:
            instance = cls()
            self.scenarios[instance.name] = instance

    def register(self, scenario: WorldScenario):
        self.scenarios[scenario.name] = scenario

    def get(self, name: str) -> Optional[WorldScenario]:
        return self.scenarios.get(name)

    def list_scenarios(self) -> List[WorldScenario]:
        return list(self.scenarios.values())
