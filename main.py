import argparse
import sys
import shutil
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.table import Table

from core.agent import FolderAgent

console = Console()

ASCII_BANNER = r"""
    ____     __    __          ___                    __ 
   / __/___ / /___/ /__  _____/   |  ____ ____  ____/ /_
  / /_/ __ \/ / __  / _ \/ ___/ /| | / __ `/ _ \/ __  / __/
 / __/ /_/ / / /_/ /  __/ /  / ___ |/ /_/ /  __/ / / / /_  
/_/  \____/_/\__,_/\___/_/  /_/  |_|\__, /\___/_/ /_/\__/  
                                   /____/                  
"""

def print_banner():
    console.print(Panel.fit(
        f"[bold blue]{ASCII_BANNER}[/bold blue]\n[cyan]                             Professional Interface[/cyan]",
        border_style="blue"
    ))

def display_memory(agent):
    console.print("\n[bold]Short-Term Memory Buffer[/bold]")
    st_store = agent.memory.get_store("short_term")
    if st_store and st_store.buffer:
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Index", style="dim", width=6)
        table.add_column("Role", style="bold green", width=12)
        table.add_column("Content")
        
        for idx, entry in enumerate(st_store.buffer):
            role = entry["metadata"].get("role", "unknown")
            # We truncate content for display if it's too long
            content = entry["content"]
            if len(content) > 500:
                content = content[:497] + "..."
            table.add_row(str(idx), role.upper(), content)
            
        console.print(table)
    else:
        console.print("[dim](Memory buffer is empty)[/dim]")

def run_query(agent, query: str):
    console.print(f"\n[dim]Executing...[/dim]")
    try:
        with console.status("[bold blue]Agent is thinking and processing tasks...", spinner="bouncingBar"):
            results = agent.execute(query)
            
        console.print(Panel("[bold]Execution Results[/bold]", style="green"))
        
        for idx, res in enumerate(results):
            task_name = res.get('task', 'Unknown Task')
            skill_name = res.get('skill', 'unknown').upper()
            result_text = res.get('result', '')
            
            console.print(f"\n[bold magenta]Step {idx} [[cyan]{skill_name}[/cyan]]:[/bold magenta] {task_name}")
            console.print(Panel(Markdown(result_text), border_style="dim"))
            
    except Exception as e:
        console.print(f"[bold red]Execution failed:[/bold red] {e}")

def main():
    parser = argparse.ArgumentParser(description="FolderAgent CLI")
    parser.add_argument("query", nargs="*", help="Optional initial query to run. If provided, the agent runs this and then enters interactive mode (unless --no-interactive is set).")
    parser.add_argument("--model", default="mistral-nemo:latest", help="Model name to use (default: mistral-nemo:latest)")
    parser.add_argument("--memory-dir", default="./memory", help="Path to memory directory (default: ./memory)")
    parser.add_argument("--capabilities-dir", default="./capabilities", help="Path to capabilities directory (default: ./capabilities)")
    parser.add_argument("--max-workers", type=int, default=3, help="Maximum number of workers (default: 3)")
    parser.add_argument("--no-interactive", action="store_true", help="Exit after running the initial query instead of entering the REPL")
    parser.add_argument("--clear-memory", action="store_true", help="Clear the memory directory on startup")
    
    args = parser.parse_args()

    print_banner()
    
    project_root = Path(__file__).resolve().parent
    memory_root = Path(args.memory_dir).resolve()
    capabilities_root = Path(args.capabilities_dir).resolve()
    
    if args.clear_memory:
        if memory_root.exists():
            try:
                shutil.rmtree(memory_root)
                console.print(f"[green]Cleared memory at {memory_root}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to clear memory: {e}[/red]")
    
    with console.status(f"[bold green]Initializing FolderAgent with {args.model}...[/bold green]", spinner="dots"):
        try:
            agent = FolderAgent(
                model_name=args.model,
                memory_root=str(memory_root),
                capabilities_root=str(capabilities_root),
                max_workers=args.max_workers
            )
        except Exception as e:
            console.print(f"[bold red]Error initializing agent:[/bold red] {e}")
            sys.exit(1)
            
    console.print(f"[bold cyan]Registered Capabilities:[/bold cyan] {', '.join(agent.capabilities.keys())}")
    console.print(f"[dim]Memory Root: {memory_root}[/dim]")
    console.print(f"[dim]Capabilities Root: {capabilities_root}[/dim]\n")
    
    initial_query = " ".join(args.query).strip() if args.query else None
    
    if initial_query:
        run_query(agent, initial_query)
        if args.no_interactive:
            return

    console.print("[bold]Interactive Mode[/bold]")
    console.print("Type your query. Special commands: [bold yellow]/exit[/bold yellow], [bold yellow]/memory[/bold yellow], [bold yellow]/clear[/bold yellow]\n")

    while True:
        try:
            query = Prompt.ask("[bold blue]Agent[/bold blue]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            break
            
        if not query:
            continue
            
        if query.lower() in ('/exit', 'exit', 'quit', '/quit'):
            console.print("[bold green]Goodbye![/bold green]")
            break
            
        if query.lower() in ('/clear', 'clear'):
            agent.memory.clear()
            console.print("[bold green]Short-term memory buffer cleared.[/bold green]")
            continue
            
        if query.lower() in ('/memory', 'memory'):
            display_memory(agent)
            continue
            
        run_query(agent, query)

if __name__ == "__main__":
    main()
