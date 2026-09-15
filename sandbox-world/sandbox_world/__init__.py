"""SandboxWorld: A secure, hardened Docker sandbox and simulated world exploration engine for AI agents."""

from sandbox_world.config import SandboxConfig
from sandbox_world.security import (
    SandboxError,
    SecurityViolationError,
    validate_security_policy,
    validate_mount,
    build_docker_security_args
)
from sandbox_world.manager import DockerSandbox, ExecutionResult
from sandbox_world.observer import (
    WorldObserver,
    WorldSnapshot,
    WorldDelta,
    ActionRecord
)
from sandbox_world.world import (
    WorldScenario,
    ScenarioResult,
    ScenarioManager,
    BrokenPipelineScenario,
    SystemAuditScenario,
    IncidentResponseScenario
)
from sandbox_world.hud import ExplorerHUD

__version__ = "0.1.0"

__all__ = [
    "SandboxConfig",
    "DockerSandbox",
    "ExecutionResult",
    "SandboxError",
    "SecurityViolationError",
    "validate_security_policy",
    "validate_mount",
    "build_docker_security_args",
    "WorldObserver",
    "WorldSnapshot",
    "WorldDelta",
    "ActionRecord",
    "WorldScenario",
    "ScenarioResult",
    "ScenarioManager",
    "BrokenPipelineScenario",
    "SystemAuditScenario",
    "IncidentResponseScenario",
    "ExplorerHUD"
]
