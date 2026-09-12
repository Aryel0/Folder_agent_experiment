import sys
import os
import builtins
from pathlib import Path
import sys
import sqlite3

print("Python executable:", sys.executable)
print("Python version:", sys.version)
print("SQLite version:", sqlite3.sqlite_version)

# Add project root to path
sys.path.insert(0, r"c:\Users\steph\Documents\Lab\experiment801")

# Auto-approve Python sandboxing for tests
builtins.input = lambda prompt: "y"

from core.agent import FolderAgent

def run_safe_test():
    print("--- Running Safe Data Analyst Test ---")
    
    # Create an isolated output directory
    output_dir = Path(r"c:\Users\steph\Documents\Lab\experiment801\tests\playground\analyst_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    agent = FolderAgent(
        model_name="phi4:latest", 
        capabilities_root=r"c:\Users\steph\Documents\Lab\experiment801\capabilities"
    )
    
    # Prompt explicitly forcing all outputs to the safe folder
    prompt = f"""You are a Data Analyst. Perform an Exploratory Data Analysis on C:\\Users\\steph\\Documents\\Lab\\experiment801\\tests\\housing.csv.

CRITICAL INSTRUCTIONS:
1. Write a SINGLE Python script using pandas and matplotlib.
2. Find the top 3 most correlated features with median_house_value.
3. Generate 3 distinct charts (e.g., histogram, scatter plot, correlation matrix).
4. You MUST physically save the charts using `plt.savefig()` to this exact directory: {output_dir}
5. Write your final report."""

    print(f"User: {prompt}\n")
    print("Processing (this may take a minute)...\n")
    
    # Catch and execute
    try:
        result = agent.execute(prompt)
        
        # Write the final JSON/String output of the agent to a file
        report_path = output_dir / "final_report.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(str(result))
            
        print(f"SUCCESS! Output successfully caught and saved.")
        print(f"Check {output_dir} for the final_report.txt and generated charts.")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    run_safe_test()
