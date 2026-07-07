# pyrefly: ignore [missing-import]
import ollama
from utils.logger import get_logger

logger = get_logger(__name__)

class Context_Manager:
    def __init__(self, max_tokens=4000, model_name="llama3"):
        self.context = {}
        self.max_tokens = max_tokens
        self.model_name = model_name
        
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using a simple heuristic."""
        return len(text) // 4

    def _get_history_tokens(self, history: list) -> int:
        """Calculate total tokens for a history array."""
        total_text = " ".join([str(msg.get("content", "")) for msg in history])
        return self._estimate_tokens(total_text)

    def get_context(self, history: list) -> list:
        """
        Get the context from the history. If history is too long, prune/summarize it.
        """
        return self.update_context(history)

    def update_context(self, history: list) -> list:
        """
        Update the context window by sliding it deleting oldest messages.
        
        Args:
            history (list): The history of the conversation.
        Returns:
            list: The updated/pruned history.
        """
        if self._get_history_tokens(history) <= self.max_tokens:
            return history

        logger.info(f"Context window exceeded {self.max_tokens} tokens. Pruning...")
        
        # Keep the system prompt / first user prompt (index 0)
        # and the latest 2 messages
        if len(history) <= 3:
            return self.summarize(history)
            
        middle_messages = history[1:-2]
        
        # Simple sliding window: drop the oldest middle message
        pruned_history = [history[0]] + middle_messages[1:] + history[-2:]
        
        if self._get_history_tokens(pruned_history) > self.max_tokens:
             return self.summarize(history)
             
        return pruned_history

    def summarize(self, history: list) -> list:
        """
        Summarize the middle of the context window and reset it.
        
        Args:
            history (list): The history of the conversation.
            
        Returns:
            list: The summarized context of the conversation.
        """
        logger.info("Running summarization on context history...")
        
        if len(history) <= 2:
            return history
            
        middle_messages = history[1:-1]
        
        text_to_summarize = ""
        for msg in middle_messages:
            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))
            # Truncate to avoid blowing up the summarization call itself
            if len(content) > 10000:
                content = content[:5000] + "\n...[TRUNCATED]...\n" + content[-5000:]
            text_to_summarize += f"[{role}]: {content}\n"
            
        prompt = f"Please briefly summarize the following conversation and tool execution steps. Focus on what was achieved, what errors occurred, and what data was discovered. Do not exceed 3 paragraphs.\n\n{text_to_summarize}"
        
        try:
            response = ollama.generate(model=self.model_name, prompt=prompt)
            summary = response.get("response", "Failed to generate summary.")
        except Exception as e:
            logger.error(f"Error during summarization: {e}")
            summary = "Summary generation failed due to error."
            
        summarized_history = [
            history[0],
            {"role": "system", "content": f"Context summarized from previous steps:\n{summary}"},
            history[-1]
        ]
        
        return summarized_history