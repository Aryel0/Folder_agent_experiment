from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.layout import Layout
from rich.text import Text

from sandbox_world.observer import WorldObserver, ActionRecord, WorldDelta
from sandbox_world.world import WorldScenario


class ExplorerHUD:
    """Real-time Heads-Up Display for observing the agent exploring the simulated world."""

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.start_time = time.time()

    def create_layout(
        self,
        scenario: Optional[WorldScenario],
        observer: WorldObserver,
        current_hypothesis: str = "Exploring environment..."
    ) -> Layout:
        """Construct the Rich Layout representing the live Explorer HUD."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=4),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=4)
        )
        layout["body"].split_row(
            Layout(name="actions", ratio=3),
            Layout(name="world_state", ratio=2)
        )

        elapsed = time.time() - self.start_time
        title_text = Text()
        if scenario:
            title_text.append(f"SIMULATED WORLD: {scenario.name.upper()}", style="bold cyan")
            title_text.append(f"  |  Elapsed: {elapsed:.1f}s\n", style="dim")
            brief = scenario.briefing
            if len(brief) > 120:
                brief = brief[:117] + "..."
            title_text.append(f"Mission: {brief}", style="white")
        else:
            title_text.append("SIMULATED WORLD EXPLORER HUD", style="bold cyan")
            title_text.append(f"  |  Elapsed: {elapsed:.1f}s\n", style="dim")
            title_text.append(f"Current Activity: {current_hypothesis}", style="white")

        layout["header"].update(Panel(title_text, border_style="cyan"))

        actions_table = Table(
            show_header=True,
            header_style="bold magenta",
            box=None,
            expand=True
        )
        actions_table.add_column("Step", width=6, style="dim")
        actions_table.add_column("Action", width=8, style="bold")
        actions_table.add_column("Command / Code", ratio=2)
        actions_table.add_column("Impact", width=14)
        actions_table.add_column("Time", width=6, style="dim")

        recent = observer.history[-8:]
        for r in recent:
            impact = r.delta.summary()
            if r.is_loop:
                impact = f"[bold red]LOOP![/bold red] {impact}"
            elif not r.delta.has_changes:
                impact = "[dim](no change)[/dim]"

            cmd_disp = r.command.replace("\n", " ")
            if len(cmd_disp) > 45:
                cmd_disp = cmd_disp[:42] + "..."

            actions_table.add_row(
                str(r.step),
                r.action_type,
                cmd_disp,
                impact,
                f"{r.duration:.1f}s"
            )

        layout["actions"].update(
            Panel(
                actions_table,
                title="Explorer Action & Sensory Trail",
                border_style="magenta"
            )
        )

        tree = self._build_world_tree(observer)
        layout["world_state"].update(
            Panel(
                tree,
                title="World Snapshot (/workspace)",
                border_style="green"
            )
        )

        metrics = observer.get_exploration_metrics()
        vitals_table = Table.grid(expand=True)
        vitals_table.add_column(justify="center", ratio=1)
        vitals_table.add_column(justify="center", ratio=1)
        vitals_table.add_column(justify="center", ratio=1)
        vitals_table.add_column(justify="center", ratio=1)
        vitals_table.add_column(justify="center", ratio=1)

        vitals_table.add_row(
            f"[bold]Total Steps:[/bold] {metrics['total_steps']}",
            f"[bold]Unique Actions:[/bold] {metrics['unique_commands']}",
            f"[bold]Loop Count:[/bold] [{'red' if metrics['loop_count'] > 0 else 'green'}]{metrics['loop_count']}[/]",
            f"[bold]Files Created/Mod:[/bold] [green]+{metrics['files_created']}[/] / [yellow]~{metrics['files_modified']}[/]",
            f"[bold]Efficiency:[/bold] [bold cyan]{metrics['exploration_efficiency_pct']}%[/bold cyan]"
        )

        layout["footer"].update(
            Panel(vitals_table, title="Exploration Vitals", border_style="blue")
        )

        return layout

    def _build_world_tree(self, observer: WorldObserver) -> Tree:
        root_path = observer.workspace_dir
        tree = Tree(f"[bold green]/workspace[/bold green]")

        if not root_path.exists():
            tree.add("[red](workspace directory does not exist)[/red]")
            return tree

        delta = observer.total_world_delta()
        created_set = set(delta.created)
        modified_set = set(delta.modified)

        dir_nodes = {"": tree}
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            rel_root = Path(root).relative_to(root_path).as_posix()
            if rel_root == ".":
                rel_root = ""

            curr_node = dir_nodes.get(rel_root, tree)

            for d in sorted(dirs):
                sub_rel = f"{rel_root}/{d}" if rel_root else d
                dir_nodes[sub_rel] = curr_node.add(f"[bold blue]{d}/[/bold blue]")

            for f in sorted(files):
                if f.startswith("."):
                    continue
                file_rel = f"{rel_root}/{f}" if rel_root else f
                if file_rel in created_set:
                    curr_node.add(f"[green]+ {f} [NEW][/green]")
                elif file_rel in modified_set:
                    curr_node.add(f"[yellow]~ {f} [MODIFIED][/yellow]")
                else:
                    curr_node.add(f"[dim]{f}[/dim]")

        return tree

    def render_once(
        self,
        scenario: Optional[WorldScenario],
        observer: WorldObserver,
        current_hypothesis: str = ""
    ):
        layout = self.create_layout(scenario, observer, current_hypothesis)
        self.console.print(layout)
