import logging
import json
from typing import Dict, Any

# pyrefly: ignore [missing-import]
try:
    import ollama
except ImportError:
    pass

from core.agent import FolderAgent
from utils.logger import get_logger

logger = get_logger(__name__)

class DualModelAgent(FolderAgent):
    """An Agent that uses a tiny model for routing and a heavy model for task execution.
    """
    
    def __init__(self, heavy_model: str = "mistral-nemo:latest", router_model: str = "llama3.2:1b", **kwargs):
        # Initialize FolderAgent with heavy_model
        # Use kwargs to pass memory_root, capabilities_root, max_workers etc if provided.
        model_name = kwargs.pop("model_name", heavy_model)
        super().__init__(model_name=model_name, **kwargs)
        self.heavy_model = model_name
        self.router_model = router_model

    def summarizer_daemon(self, raw_text: str) -> str:
        """Background daemon that compresses large text using the tiny model."""
        if len(raw_text) < 500:
            return raw_text # No need to summarize
            
        logger.info(f"Summarizer Daemon active: compressing text of length {len(raw_text)}...")
        prompt = (
            "You are a background summarization daemon.\n"
            "Compress the following text into 3-5 concise bullet points containing only the critical facts, data, or code summaries needed for context.\n\n"
            f"TEXT TO COMPRESS:\n{raw_text}\n\n"
            "BULLET POINTS:"
        )
        
        try:
            response = ollama.generate(
                model=self.router_model,
                prompt=prompt,
                format=""
            )
            return response.get("response", raw_text)
        except Exception as e:
            logger.error(f"Daemon failed: {e}")
            return raw_text
        
    def _route_request(self, user_input: str) -> str:
        """Uses the tiny, fast model to route the request."""
        logger.info(f"Routing request using tiny model: {self.router_model}")
        
        # Prepare the capability descriptions for the prompt
        cap_descriptions = {}
        for name, cap in self.capabilities.items():
            manifest = cap.get("manifest", {})
            cap_descriptions[name] = manifest.get("tagline", manifest.get("description", "No description available."))
            
        prompt = (
            "You are an intelligent router for an autonomous agent system.\n"
            "Your job is to read the user's request and decide which single capability is best suited to handle it.\n\n"
            f"Available capabilities:\n{json.dumps(cap_descriptions, indent=2)}\n\n"
            "CRITICAL RULES:\n"
            "1. If the request is simple and can be fully completed by a SINGLE capability (e.g., general conversation -> chat, simple script -> coder), output that capability's name.\n"
            "2. If the request contains MULTIPLE actions, uses words like 'and', 'then', or asks to create multiple different files/outputs, you MUST output 'planner'.\n"
            "3. If the request requires researching something AND writing about it, you MUST output 'planner'.\n"
            "4. If you are unsure or the task feels remotely complex, output 'planner'.\n\n"
            "Respond ONLY with a valid JSON object in this format:\n"
            "{\n  \"selected_capability\": \"capability_name\"\n}\n\n"
            f"User Request: {user_input}"
        )
        
        try:
            # Inference using the tiny model
            response = ollama.generate(
                model=self.router_model,
                prompt=prompt,
                format="json"
            )
            result = json.loads(response.get("response", "{}"))
            selected = result.get("selected_capability", "planner")
            
            # Validate the LLM output
            if selected not in self.capabilities and selected != "planner":
                logger.warning(f"Router returned unknown capability '{selected}'. Defaulting to planner.")
                return "planner"
                
            logger.info(f"Router selected: {selected}")
            return selected
            
        except Exception as e:
            logger.error(f"Routing failed: {e}. Defaulting to planner.")
            return "planner"

# Example Usage:
if __name__ == "__main__":
    agent = DualModelAgent()
    print("Agent initialized with:", agent.heavy_model, "and", agent.router_model)
