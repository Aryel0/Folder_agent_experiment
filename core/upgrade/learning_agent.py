from __future__ import annotations
import json
# pyrefly: ignore [missing-import]
import ollama
from core.agent import FolderAgent
from advancement.parallel_agent import ParallelFolderAgent
from utils.logger import get_logger

logger = get_logger(__name__)


class LearningMixin:
    """Mixin class to add self-reflection and learning capabilities to folder agents."""

    # pyrefly: ignore [invalid-annotation]
    def reflect_on_execution(self: FolderAgent, user_input: str, results: list[dict]) -> None:
        """Run an LLM-based reflection step to extract lessons learned and store them."""
        logger.info("Starting execution reflection loop to extract lessons learned...")
        
        # Build execution transcript summary
        history_summary = []
        for idx, r in enumerate(results):
            task_desc = r.get("task", "")
            skill = r.get("skill", "")
            result = str(r.get("result", ""))
            # Truncate result if it is too large
            if len(result) > 2000:
                result = result[:1000] + "\n...[TRUNCATED]...\n" + result[-1000:]
            history_summary.append(
                f"Task {idx}: {task_desc}\n"
                f"Skill Used: {skill}\n"
                f"Result:\n{result}"
            )
        
        summary_text = "\n\n".join(history_summary)
        
        prompt = (
            f"You are a meta-cognition assistant. Analyze the following task execution transcript for the user goal: '{user_input}'\n\n"
            f"Execution Details:\n{summary_text}\n\n"
            "Extract 1 to 3 key lessons, tips, or facts learned from this execution "
            "(e.g., successful commands/patterns, syntax/path fixes, or tool limits to avoid). "
            "Keep each lesson concise (1-2 sentences). "
            "Write your response as a simple JSON list of strings. Do not include markdown formatting or extra text outside the JSON list."
        )

        try:
            response = ollama.generate(model=self.model, prompt=prompt, format="json")
            lessons_text = response.get("response", "[]")
            lessons = json.loads(lessons_text)
            
            if isinstance(lessons, list):
                added_count = 0
                for lesson in lessons:
                    if isinstance(lesson, str) and lesson.strip():
                        self.memory.add("long_term", lesson, {"category": "lessons_learned"})
                        added_count += 1
                if added_count > 0:
                    self.memory.save()
                    logger.info(f"Successfully saved {added_count} lessons learned to long-term memory.")
            else:
                logger.warning(f"Unexpected reflection response type (not a list): {type(lessons)}")
        except Exception as e:
            logger.error(f"Error during self-reflection: {e}")


class LearningFolderAgent(LearningMixin, FolderAgent):
    """A FolderAgent subclass that automatically learns lessons from sequential execution runs."""

    def execute(self, user_input: str) -> list[dict]:
        results = super().execute(user_input)
        if results:
            self.reflect_on_execution(user_input, results)
        return results


class ParallelLearningFolderAgent(LearningMixin, ParallelFolderAgent):
    """A ParallelFolderAgent subclass that automatically learns lessons from concurrent execution runs."""

    def execute(self, user_input: str) -> list[dict]:
        results = super().execute(user_input)
        if results:
            self.reflect_on_execution(user_input, results)
        return results
