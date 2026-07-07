import sys
from pathlib import Path

# Add parent directory to path so we can import the agent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.upgrade.parallel_agent import ParallelFolderAgent

def run_complex_test():
    print("=" * 60)
    print("         COMPLEX TASK & AGGREGATOR TEST")
    print("=" * 60)
    
    playground_dir = Path(__file__).resolve().parent
    sandbox_memory_root = playground_dir / "sandbox_memory"
    
    print("Initializing ParallelFolderAgent...")
    try:
        agent = ParallelFolderAgent(
            model_name="mistral-nemo:latest",
            memory_root=str(sandbox_memory_root),
            capabilities_root=str(playground_dir.parent.parent / "capabilities"),
            max_workers=2  # Using 2 to allow safe parallel execution
        )
    except Exception as e:
        print(f"Error initializing agent: {e}")
        return

    complex_query = (
        "Research the top 3 best practices for Python concurrency. "
        "At the same time, analyze our core/agent.py file to understand how it currently works. "
        "Finally, write a short guide explaining how our codebase compares to those best practices."
    )
    
    print(f"\n[QUERY]\n{complex_query}\n")
    print("-" * 60)
    print("Sending to Planner...\n")
    
    try:
        results = agent.execute(complex_query)
        
        print("\n" + "=" * 50)
        print("                 FINAL PIPELINE RESULTS")
        print("=" * 50)
        for idx, res in enumerate(results):
            print(f"\n--- Step {idx} [{res['skill'].upper()}] ---")
            print(f"Task: {res['task']}")
            print(f"Result (truncated):\n{str(res['result'])[:500]}...")
            print("-" * 50)
            
    except Exception as e:
        print(f"\nExecution failed with error: {e}")

if __name__ == "__main__":
    run_complex_test()
