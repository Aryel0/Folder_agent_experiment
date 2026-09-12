import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from core.agent import FolderAgent
from utils.logger import get_logger

logger = get_logger("test_jarvis")

def test_jarvis():
    agent = FolderAgent(model_name="mistral-nemo:latest")
    
    # We will give it a query that only Jarvis should handle.
    query = "Use Jarvis to find out what OS I am running, and what Python version is executing this script."
    
    logger.info(f"Sending query: {query}")
    results = agent.execute(query)
    
    for result in results:
        logger.info(f"Result: {result}")

if __name__ == "__main__":
    test_jarvis()
