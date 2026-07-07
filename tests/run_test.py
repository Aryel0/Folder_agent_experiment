import json
import sys
import os
from pathlib import Path

# Add the parent directory to the Python path to import the agent module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.agent import FolderAgent
def run_test():
    # Instantiate the agent using mistral-nemo:latest
    print("Initializing FolderAgent with model 'mistral-nemo:latest'...")
    agent = FolderAgent(model_name="mistral-nemo:latest")

    # Display registered capabilities
    print(f"Registered capabilities: {list(agent.capabilities.keys())}\n")

    # The user request that requires multiple steps:
    # First plan it, then write a short poem about the plan.
    user_request = "Plan a task to list the files in the directory and read README.md, then write a short poem about this process."
    print(f"Executing Multi-step request: {user_request!r}\n")

    # Run the full pipeline execution
    execution_results = agent.execute(user_request)

    print("\n=== Execution Pipeline Results ===")
    for idx, res in enumerate(execution_results):
        print(f"\nStep {idx} [{res['skill']}]: {res['task']}")
        print(f"Result:\n{res['result']}")
        print("="*40)

    # Monitor/print short-term memory of the session
    print("\n--- Short-Term Memory Buffer ---")
    st_store = agent.memory.get_store("short_term")
    if st_store:
        for idx, entry in enumerate(st_store.buffer):
            role = entry["metadata"].get("role", "unknown")
            print(f"Entry {idx} [{role}]:")
            print(entry["content"])
            print("-" * 30)

if __name__ == "__main__":
    run_test()
