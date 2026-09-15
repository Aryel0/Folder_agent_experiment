from __future__ import annotations
import os
import time
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Optional

logger = logging.getLogger(__name__)


@dataclass
class FileMeta:
    """Metadata representation of a file in the simulated world."""
    rel_path: str
    size: int
    content_hash: str
    mtime: float


@dataclass
class WorldDelta:
    """Represents differences in the simulated world between two points in time."""
    created: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.created or self.modified or self.deleted)

    def summary(self) -> str:
        parts = []
        if self.created:
            parts.append(f"+{len(self.created)} created")
        if self.modified:
            parts.append(f"~{len(self.modified)} modified")
        if self.deleted:
            parts.append(f"-{len(self.deleted)} deleted")
        return ", ".join(parts) or "no changes"


class WorldSnapshot:
    """Point-in-time state of all files and directories inside the sandbox workspace."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.timestamp = time.time()
        self.files: Dict[str, FileMeta] = {}
        self._capture()

    def _hash_file(self, path: Path) -> str:
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            return h.hexdigest()[:16]
        except Exception:
            return ""

    def _capture(self):
        if not self.workspace_dir.exists():
            return

        for root, dirs, filenames in os.walk(self.workspace_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in filenames:
                if fname.startswith("."):
                    continue
                file_path = Path(root) / fname
                try:
                    rel_path = file_path.relative_to(self.workspace_dir).as_posix()
                    stat = file_path.stat()
                    self.files[rel_path] = FileMeta(
                        rel_path=rel_path,
                        size=stat.st_size,
                        content_hash=self._hash_file(file_path),
                        mtime=stat.st_mtime
                    )
                except Exception as e:
                    logger.debug(f"Could not snapshot file {file_path}: {e}")

    def diff(self, previous: WorldSnapshot) -> WorldDelta:
        """Compute differences compared to an earlier snapshot."""
        delta = WorldDelta()

        for path, meta in self.files.items():
            if path not in previous.files:
                delta.created.append(path)
            elif (meta.content_hash != previous.files[path].content_hash or
                  meta.size != previous.files[path].size):
                delta.modified.append(path)

        for path in previous.files:
            if path not in self.files:
                delta.deleted.append(path)

        delta.created.sort()
        delta.modified.sort()
        delta.deleted.sort()
        return delta


@dataclass
class ActionRecord:
    """Telemetry record for a single action executed by the explorer in the world."""
    step: int
    action_type: str
    command: str
    output_snippet: str
    delta: WorldDelta
    duration: float
    is_loop: bool = False
    timestamp: float = field(default_factory=time.time)


class WorldObserver:
    """Monitors the agent's actions and state mutations within the simulated world."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.initial_snapshot = WorldSnapshot(str(self.workspace_dir))
        self.current_snapshot = self.initial_snapshot
        self.history: List[ActionRecord] = []
        self.visited_paths: Set[str] = set()
        self.step_counter = 0

    def reset(self):
        """Reset observer tracking for a new scenario or session."""
        self.initial_snapshot = WorldSnapshot(str(self.workspace_dir))
        self.current_snapshot = self.initial_snapshot
        self.history.clear()
        self.visited_paths.clear()
        self.step_counter = 0

    def detect_loop(self, command: str, window: int = 4) -> bool:
        """Detect if the explorer is repeating identical commands or thrashing in place."""
        clean_cmd = command.strip()
        recent_commands = [
            rec.command.strip() for rec in self.history[-window:]
        ]
        return recent_commands.count(clean_cmd) >= 2

    def record_action(
        self,
        action_type: str,
        command: str,
        output: str,
        duration: float
    ) -> ActionRecord:
        """Capture the effect of an action on the simulated world."""
        self.step_counter += 1
        new_snapshot = WorldSnapshot(str(self.workspace_dir))
        delta = new_snapshot.diff(self.current_snapshot)
        self.current_snapshot = new_snapshot

        for p in delta.created + delta.modified:
            self.visited_paths.add(p)

        is_loop = self.detect_loop(command)

        snippet = output.strip()
        if len(snippet) > 250:
            snippet = snippet[:247] + "..."

        record = ActionRecord(
            step=self.step_counter,
            action_type=action_type,
            command=command.strip(),
            output_snippet=snippet,
            delta=delta,
            duration=duration,
            is_loop=is_loop
        )
        self.history.append(record)
        return record

    def total_world_delta(self) -> WorldDelta:
        """Compute the total delta from the initial snapshot to the current state."""
        return self.current_snapshot.diff(self.initial_snapshot)

    def get_exploration_metrics(self) -> dict:
        """Calculate quantitative metrics on the agent's exploration quality."""
        total_steps = len(self.history)
        if total_steps == 0:
            return {
                "total_steps": 0,
                "unique_commands": 0,
                "loop_count": 0,
                "loop_rate_pct": 0.0,
                "files_created": 0,
                "files_modified": 0,
                "files_deleted": 0,
                "visited_paths_count": 0,
                "actions_with_state_impact": 0,
                "exploration_efficiency_pct": 100.0
            }

        loop_count = sum(1 for r in self.history if r.is_loop)
        total_delta = self.total_world_delta()
        
        unique_commands = len(set(r.command for r in self.history))
        actions_with_state_impact = sum(1 for r in self.history if r.delta.has_changes)

        loop_penalty = (loop_count / total_steps) * 50.0
        diversity_factor = min(1.0, unique_commands / total_steps)
        efficiency = max(0.0, min(100.0, (diversity_factor * 100.0) - loop_penalty))

        return {
            "total_steps": total_steps,
            "unique_commands": unique_commands,
            "loop_count": loop_count,
            "loop_rate_pct": round((loop_count / total_steps) * 100.0, 1),
            "files_created": len(total_delta.created),
            "files_modified": len(total_delta.modified),
            "files_deleted": len(total_delta.deleted),
            "visited_paths_count": len(self.visited_paths),
            "actions_with_state_impact": actions_with_state_impact,
            "exploration_efficiency_pct": round(efficiency, 1)
        }
