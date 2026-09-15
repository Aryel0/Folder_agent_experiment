#!/usr/bin/env python3
"""Unified CLI tool for the standalone sandbox_world package."""
from __future__ import annotations
import sys
import argparse
import subprocess
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from sandbox_world.config import SandboxConfig
from sandbox_world.manager import DockerSandbox
from sandbox_world.observer import WorldObserver
from sandbox_world.world import ScenarioManager, ScenarioResult
from sandbox_world.hud import ExplorerHUD

console = Console()


def main():
    parser = argparse.ArgumentParser(
        prog="sandbox-world",
        description="Unified CLI for Docker Sandbox & Simulated World Exploration."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Lifecycle & status commands
    subparsers.add_parser("status", help="Probe Docker availability and sandbox health")
    subparsers.add_parser("build", help="Build the Docker sandbox image")
    subparsers.add_parser("create", help="Create the hardened sandbox container")
    subparsers.add_parser("start", help="Start the sandbox container")
    subparsers.add_parser("stop", help="Stop the sandbox container")
    subparsers.add_parser("destroy", help="Destroy the sandbox container")
    subparsers.add_parser("reset", help="Reset container to a clean, fresh state")

    # Execution commands
    exec_parser = subparsers.add_parser("exec", help="Run a shell command inside the sandbox")
    exec_parser.add_argument("cmd", type=str, help="Command string to execute")
    exec_parser.add_argument("--timeout", type=int, default=30, help="Execution timeout in seconds")

    py_parser = subparsers.add_parser("py", help="Run Python code inside the sandbox")
    py_parser.add_argument("code", type=str, help="Python code string to execute")
    py_parser.add_argument("--timeout", type=int, default=30, help="Execution timeout in seconds")

    # Evaluation commands
    eval_parser = subparsers.add_parser("eval", help="Run and evaluate simulated world exploration scenarios")
    eval_parser.add_argument("--scenario", type=str, default="all", help="Scenario to run ('all' or specific name)")
    eval_parser.add_argument("--workspace", type=str, default="./sandbox_workspace", help="Workspace path")
    eval_parser.add_argument("--dry-run", action="store_true", default=False, help="Run simulated explorer actions")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    sandbox = DockerSandbox()

    if args.command == "status":
        info = sandbox.status()
        console.print("\n=== Sandbox World Status ===")
        for k, v in info.items():
            console.print(f"  {k:20}: {v}")
        console.print()

    elif args.command == "build":
        dockerfile = Path(__file__).parent.parent / "docker" / "Dockerfile.sandbox"
        console.print(f"Building Docker sandbox image from {dockerfile}...")
        res = subprocess.run(["docker", "build", "-t", sandbox.config.image_name, "-f", str(dockerfile), "."])
        sys.exit(res.returncode)

    elif args.command == "create":
        sandbox.create()
        console.print(f"[green][SUCCESS][/green] Sandbox container '{sandbox.config.container_name}' created.")

    elif args.command == "start":
        sandbox.start()
        console.print(f"[green][SUCCESS][/green] Sandbox container '{sandbox.config.container_name}' started.")

    elif args.command == "stop":
        sandbox.stop()
        console.print(f"[green][SUCCESS][/green] Sandbox container '{sandbox.config.container_name}' stopped.")

    elif args.command == "destroy":
        sandbox.destroy()
        console.print(f"[green][SUCCESS][/green] Sandbox container '{sandbox.config.container_name}' destroyed.")

    elif args.command == "reset":
        sandbox.reset()
        console.print(f"[green][SUCCESS][/green] Sandbox container '{sandbox.config.container_name}' reset.")

    elif args.command == "exec":
        res = sandbox.execute_command(args.cmd, timeout=args.timeout)
        print(res.output())
        sys.exit(res.exit_code)

    elif args.command == "py":
        res = sandbox.execute_python(args.code, timeout=args.timeout)
        print(res.output())
        sys.exit(res.exit_code)

    elif args.command == "eval":
        manager = ScenarioManager()
        scenarios = manager.list_scenarios() if args.scenario == "all" else [manager.get(args.scenario)]
        if not scenarios or scenarios[0] is None:
            console.print(f"[red]Error: Unknown scenario '{args.scenario}'[/red]")
            sys.exit(1)

        ws_path = Path(args.workspace).resolve()
        hud = ExplorerHUD(console)
        results: list[ScenarioResult] = []

        for sc in scenarios:
            ws_path.mkdir(parents=True, exist_ok=True)
            sc.setup(str(ws_path))
            observer = WorldObserver(str(ws_path))
            hud.render_once(sc, observer, "Evaluating scenario...")

            # If dry-run, execute a mock exploration sequence
            if args.dry_run:
                observer.record_action("bash", "ls -la", "Found files", 0.05)
                if sc.name == "broken_pipeline":
                    pipeline_file = ws_path / "data_pipeline.py"
                    pipeline_file.write_text(pipeline_file.read_text().replace(
                        'total_cpu += float(row["cpu_pct"])',
                        'if row["cpu_pct"] != "N/A": total_cpu += float(row["cpu_pct"])'
                    ))
                    observer.record_action("files", "repair pipeline", "OK", 0.05)
                    subprocess.run([sys.executable, str(pipeline_file)], cwd=str(ws_path), capture_output=True)
                    observer.record_action("bash", "python data_pipeline.py", "Finished", 0.1)
                elif sc.name == "system_audit":
                    (ws_path / "decoded_key.txt").write_text("UplinkSecret2026")
                    observer.record_action("files", "write key", "OK", 0.05)
                elif sc.name == "incident_response":
                    import json
                    (ws_path / "incident_report.json").write_text(json.dumps({
                        "attacker_ip": "198.51.100.42",
                        "attack_type": "SQL Injection"
                    }))
                    observer.record_action("files", "write report", "OK", 0.05)

            hud.render_once(sc, observer, "Scenario finished.")
            res = sc.verify(str(ws_path), "Completed", observer)
            results.append(res)

        # Scorecard
        table = Table(title="SIMULATED WORLD EXPLORATION SCORECARD", show_lines=True)
        table.add_column("Scenario", style="bold cyan")
        table.add_column("Result", justify="center")
        table.add_column("Score", justify="center")
        table.add_column("Steps", justify="center")
        table.add_column("Loops", justify="center")
        table.add_column("Efficiency", justify="center")

        for r in results:
            badge = "[green]PASS[/green]" if r.success else "[red]FAIL[/red]"
            m = r.metrics
            table.add_row(
                r.scenario_name,
                badge,
                f"{r.score:.1f}%",
                str(m.get("total_steps", 0)),
                str(m.get("loop_count", 0)),
                f"{m.get('exploration_efficiency_pct', 0.0)}%"
            )
        console.print(table)


if __name__ == "__main__":
    main()
