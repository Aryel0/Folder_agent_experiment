#!/usr/bin/env python3
"""CLI utility to manage and inspect the AI Agent Docker Sandbox."""
import sys
import argparse
import subprocess
from core.sandbox import DockerSandbox, SandboxConfig, SecurityViolationError


def main():
    parser = argparse.ArgumentParser(
        description="Manage the AI Agent isolated Docker sandbox."
    )
    subparsers = parser.add_subparsers(dest="command", help="Sandbox command to execute")

    # Status
    subparsers.add_parser("status", help="Inspect sandbox status and Docker daemon health")

    # Build
    subparsers.add_parser("build", help="Build the Docker sandbox image (agent-sandbox:latest)")

    # Lifecycle commands
    subparsers.add_parser("create", help="Create the sandbox container with strict security settings")
    subparsers.add_parser("start", help="Start the sandbox container")
    subparsers.add_parser("stop", help="Gracefully stop the sandbox container")
    subparsers.add_parser("destroy", help="Forcefully destroy the sandbox container")
    subparsers.add_parser("reset", help="Reset container to a clean, fresh state")

    # Execution commands
    exec_parser = subparsers.add_parser("exec", help="Run a shell command inside the sandbox")
    exec_parser.add_argument("cmd", type=str, help="Command string to execute")
    exec_parser.add_argument("--timeout", type=int, default=30, help="Execution timeout in seconds")

    py_parser = subparsers.add_parser("py", help="Run Python code inside the sandbox")
    py_parser.add_argument("code", type=str, help="Python code string to execute")
    py_parser.add_argument("--timeout", type=int, default=30, help="Execution timeout in seconds")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    sandbox = DockerSandbox()

    if args.command == "status":
        info = sandbox.status()
        print("\n=== AI Agent Sandbox Status ===")
        for k, v in info.items():
            print(f"  {k:20}: {v}")
        print()

    elif args.command == "build":
        print("Building sandbox Docker image 'agent-sandbox:latest'...")
        cmd = ["docker", "build", "-t", "agent-sandbox:latest", "-f", "docker/Dockerfile.sandbox", "."]
        res = subprocess.run(cmd)
        if res.returncode == 0:
            print("\n[SUCCESS] Sandbox image built successfully!")
        else:
            print(f"\n[ERROR] Build failed with exit code {res.returncode}")
            sys.exit(res.returncode)

    elif args.command == "create":
        sandbox.create()
        print(f"[SUCCESS] Sandbox container '{sandbox.config.container_name}' created.")

    elif args.command == "start":
        sandbox.start()
        print(f"[SUCCESS] Sandbox container '{sandbox.config.container_name}' started.")

    elif args.command == "stop":
        sandbox.stop()
        print(f"[SUCCESS] Sandbox container '{sandbox.config.container_name}' stopped.")

    elif args.command == "destroy":
        sandbox.destroy(remove_workspace=False)
        print(f"[SUCCESS] Sandbox container '{sandbox.config.container_name}' destroyed.")

    elif args.command == "reset":
        sandbox.reset()
        print(f"[SUCCESS] Sandbox container '{sandbox.config.container_name}' reset to fresh state.")

    elif args.command == "exec":
        res = sandbox.execute_command(args.cmd, timeout=args.timeout)
        print(res.output())
        sys.exit(res.exit_code)

    elif args.command == "py":
        res = sandbox.execute_python(args.code, timeout=args.timeout)
        print(res.output())
        sys.exit(res.exit_code)


if __name__ == "__main__":
    main()
