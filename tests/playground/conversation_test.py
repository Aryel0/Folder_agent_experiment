import sys
import shutil
from pathlib import Path

# Add parent directory to path so we can import the agent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.agent import FolderAgent
from core.upgrade.parallel_agent import ParallelFolderAgent
from core.upgrade.learning_agent import LearningFolderAgent

def run_test_for_agent(agent_class, name, playground_dir):
    print("\n" + "=" * 60)
    print(f"         TESTING: {name}")
    print("=" * 60)
    
    sandbox_memory_root = playground_dir / f"sandbox_memory_{name}"
    
    # Sanitize environment
    if sandbox_memory_root.exists():
        try:
            shutil.rmtree(sandbox_memory_root)
        except Exception:
            pass
            
    print(f"Initializing {name}...")
    try:
        kwargs = {
            "model_name": "mistral-nemo:latest",
            "memory_root": str(sandbox_memory_root),
            "capabilities_root": str(playground_dir.parent.parent / "capabilities")
        }
        if name == "ParallelFolderAgent":
            kwargs["max_workers"] = 2
            
        agent = agent_class(**kwargs)
    except Exception as e:
        print(f"Error initializing {name}: {e}")
        return

    # TURN 1
    query_1 = "Analyze the core/agent.py file and summarize its main purpose in exactly one sentence."
    print(f"\n[TURN 1: USER] {query_1}")
    print("-" * 60)
    try:
        results_1 = agent.execute(query_1)
        final_answer_1 = results_1[-1]['result'] if results_1 else "No result"
        print(f"\n[TURN 1: AGENT]\n{final_answer_1}")
    except Exception as e:
        print(f"\nTurn 1 failed: {e}")
        return

    # TURN 2 (Depends on context from Turn 1)
    query_2 = "Now write a python snippet that imports the main class from that file and initializes it with model_name='mistral-nemo:latest'."
    print(f"\n\n[TURN 2: USER] {query_2}")
    print("-" * 60)
    try:
        results_2 = agent.execute(query_2)
        final_answer_2 = results_2[-1]['result'] if results_2 else "No result"
        print(f"\n[TURN 2: AGENT]\n{final_answer_2}")
    except Exception as e:
        print(f"\nTurn 2 failed: {e}")

    # TURN 3 (Tests long-term context retention across multiple turns)
    query_3 = "Based on our conversation so far, what was the exact first question I asked you?"
    print(f"\n\n[TURN 3: USER] {query_3}")
    print("-" * 60)
    try:
        results_3 = agent.execute(query_3)
        final_answer_3 = results_3[-1]['result'] if results_3 else "No result"
        print(f"\n[TURN 3: AGENT]\n{final_answer_3}")
    except Exception as e:
        print(f"\nTurn 3 failed: {e}")

    # Inspect the memory buffer
    print("\n\n" + "-" * 60)
    print(f"         INSPECTING MEMORY & CHAIN OF THOUGHT: {name}")
    print("-" * 60)
    st_store = agent.memory.get_store("short_term")
    if st_store and st_store.buffer:
        for idx, entry in enumerate(st_store.buffer):
            role = entry["metadata"].get("role", "unknown")
            print(f"[{idx}] {role.upper()}:")
            # Truncate content slightly if it's too huge, but usually it's fine
            print(entry["content"])
            print("-" * 40)
    else:
        print("(Memory buffer is empty)")


def run_conversation_test():
    playground_dir = Path(__file__).resolve().parent
    
    agents_to_test = [
        (FolderAgent, "FolderAgent"),
        (ParallelFolderAgent, "ParallelFolderAgent"),
        (LearningFolderAgent, "LearningFolderAgent")
    ]
    
    for agent_class, name in agents_to_test:
        run_test_for_agent(agent_class, name, playground_dir)

if __name__ == "__main__":
    run_conversation_test()
