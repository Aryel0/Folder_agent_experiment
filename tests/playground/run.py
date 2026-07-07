import sys
import shutil
from pathlib import Path

# Add parent directory to path so we can import the agent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.agent import FolderAgent

def main():
    print("=" * 60)
    print("         AGENT SANDBOX & EVALUATION PLAYGROUND")
    print("=" * 60)
    
    # Define sanitized/isolated memory root inside playground directory
    playground_dir = Path(__file__).resolve().parent
    sandbox_memory_root = playground_dir / "sandbox_memory"
    
    # Sanitize: clear existing sandbox memory if requested or starts fresh
    if sandbox_memory_root.exists():
        try:
            shutil.rmtree(sandbox_memory_root)
        except Exception:
            pass
    
    # Initialize the FolderAgent with capabilities located in the parent directory
    # but using the isolated sandbox memory directory.
    print("Initializing FolderAgent with model 'mistral-nemo:latest'...")
    try:
        agent = FolderAgent(
            model_name="mistral-nemo:latest",
            memory_root=str(sandbox_memory_root),
            capabilities_root=str(playground_dir.parent.parent / "capabilities"),
            max_workers=3  # Increased to 3 to allow parallel execution of independent tasks
        )
    except Exception as e:
        print(f"Error initializing agent: {e}")
        return

    print(f"Registered capabilities: {list(agent.capabilities.keys())}")
    print("Sandbox memory: [SANITIZED & ISOLATED]")
    print("-" * 60)
    print("Type your query below to test the agent.")
    print("Type 'exit' to quit, 'memory' to view the short-term memory buffer, or 'clear' to reset memory.")
    print("=" * 60)

    while True:
        try:
            query = input("\nTest Query > ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not query:
            continue

        if query.lower() == 'exit':
            print("Exiting evaluation playground. Goodbye!")
            break

        if query.lower() == 'clear':
            agent.memory.clear()
            print("Short-term memory buffer cleared.")
            continue

        if query.lower() == 'memory':
            print("\n--- Short-Term Memory Buffer ---")
            st_store = agent.memory.get_store("short_term")
            if st_store and st_store.buffer:
                for idx, entry in enumerate(st_store.buffer):
                    role = entry["metadata"].get("role", "unknown")
                    print(f"[{idx}] {role.upper()}:")
                    print(entry["content"])
                    print("-" * 40)
            else:
                print("(Memory buffer is empty)")
            continue

        print("\nSending query to agent execution pipeline...")
        try:
            results = agent.execute(query)
            
            print("\n" + "=" * 50)
            print("                 EXECUTION RESULTS")
            print("=" * 50)
            for idx, res in enumerate(results):
                print(f"\nStep {idx} [{res['skill'].upper()}]: {res['task']}")
                print(f"Result:\n{res['result']}")
                print("-" * 50)
            print("=" * 50)
            
        except Exception as e:
            print(f"\nExecution failed with error: {e}")

if __name__ == "__main__":
    main()
