from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class SandboxConfig(BaseModel):
    """Configuration model for the hardened AI Agent Docker Sandbox."""

    image_name: str = Field(
        default="agent-sandbox:latest",
        description="Docker image name to use for the sandbox."
    )
    container_name: str = Field(
        default="folderagent_sandbox",
        description="Name assigned to the sandbox container."
    )
    user: str = Field(
        default="1000:1000",
        description="Non-root UID:GID for container execution."
    )
    workspace_dir: str = Field(
        default_factory=lambda: os.path.abspath("./sandbox_workspace"),
        description="Host directory mounted strictly to /workspace in container."
    )
    read_only_rootfs: bool = Field(
        default=True,
        description="Mount container root filesystem as read-only."
    )
    network_mode: str = Field(
        default="none",
        description="Network isolation mode ('none' by default, or 'bridge')."
    )
    cpu_limit: float = Field(
        default=1.0,
        description="Max CPU cores container may utilize."
    )
    memory_limit: str = Field(
        default="512m",
        description="Max RAM container may utilize."
    )
    memory_swap: str = Field(
        default="512m",
        description="Max RAM + swap. Setting equal to memory_limit disables swap."
    )
    pids_limit: int = Field(
        default=64,
        description="Max process count to prevent fork bombs."
    )
    tmpfs_tmp_size: str = Field(
        default="64m",
        description="Tmpfs size for /tmp."
    )
    tmpfs_home_size: str = Field(
        default="64m",
        description="Tmpfs size for /home/agent."
    )
    drop_capabilities: List[str] = Field(
        default_factory=lambda: ["ALL"],
        description="Linux capabilities to drop."
    )
    no_new_privileges: bool = Field(
        default=True,
        description="Prevent processes from acquiring new privileges via setuid."
    )
    seccomp_profile_path: Optional[str] = Field(
        default_factory=lambda: str(Path(__file__).parent / "seccomp_strict.json"),
        description="Path to seccomp profile JSON file."
    )
    apparmor_profile: Optional[str] = Field(
        default="docker-default",
        description="AppArmor profile name where supported."
    )
    default_timeout: int = Field(
        default=30,
        description="Default wall-clock execution timeout in seconds."
    )
    privileged: bool = Field(
        default=False,
        description="Privileged mode - MUST ALWAYS BE FALSE."
    )

    @field_validator("privileged")
    @classmethod
    def validate_privileged(cls, v: bool) -> bool:
        if v is True:
            raise ValueError(
                "SecurityViolation: Privileged containers are strictly forbidden in AI Agent Sandbox!"
            )
        return v

    @field_validator("user")
    @classmethod
    def validate_user(cls, v: str) -> str:
        if v in ("0", "root", "0:0"):
            raise ValueError(
                "SecurityViolation: Running as root (UID 0) is strictly forbidden in AI Agent Sandbox!"
            )
        return v

    @field_validator("network_mode")
    @classmethod
    def validate_network(cls, v: str) -> str:
        if v.lower() == "host":
            raise ValueError(
                "SecurityViolation: Host networking (--network host) is strictly forbidden in AI Agent Sandbox!"
            )
        return v
