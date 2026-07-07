from __future__ import annotations
import concurrent.futures
from core.agent import FolderAgent
from utils.logger import get_logger

logger = get_logger(__name__)

class ParallelFolderAgent(FolderAgent):
    """An agent that extends FolderAgent to execute its planner tasks concurrently."""

    def execute(self, user_input: str) -> list[dict]:
        """Execute a user request by first planning it, then running the tasks in parallel.
        
        This method invokes the 'planner' capability to decompose the request into a 
        dependency graph of sub-tasks. It then uses a ThreadPoolExecutor to schedule 
        and execute unblocked tasks sequentially or in parallel (governed by max_workers).
        
        Args:
            user_input (str): The overall goal or instruction from the user.
            
        Returns:
            list[dict]: A chronologically ordered list of task execution results.
            
        Raises:
            ValueError: If the 'planner' capability is not found.
            RuntimeError: If a dependency cycle or unresolvable task blockage occurs.
        """
        if "planner" not in self.capabilities:
            logger.error("Planner capability not registered.")
            raise ValueError("Planner capability not registered.")

        max_retries = 3
        attempt = 0
        tasks = None
        error_context = ""

        while attempt < max_retries:
            logger.info(f"Consulting planner to break down the request (Attempt {attempt + 1}/{max_retries})...")
            
            current_input = user_input
            if error_context:
                current_input += f"\n\nERROR FROM PREVIOUS ATTEMPT:\n{error_context}\nPlease correct your plan."
                
            plan = self.inference(current_input, context_folder=self.capabilities["planner"]["path"])
            
            if isinstance(plan, dict):
                tasks = plan.get("tasks") or plan.get("steps")
                
            if not tasks:
                error_context = "The plan did not contain a 'tasks' array."
                attempt += 1
                continue
                
            invalid_skills = []
            for t in tasks:
                skill = t.get("skill")
                if skill and skill not in self.capabilities:
                    invalid_skills.append(skill)
                    
            if invalid_skills:
                error_context = f"You used unknown capabilities: {', '.join(invalid_skills)}. Available capabilities are: {list(self.capabilities.keys())}. Review the provided manifests. You MUST use one of the existing capabilities to accomplish this step. Only if NO existing capability can possibly cover the use case should you fail the plan."
                logger.warning(error_context)
                attempt += 1
                tasks = None
            else:
                break

        if not tasks:
            raise ValueError("Planner failed to generate a valid plan with known capabilities after maximum retries. Consider creating a new capability for your specific needs.")

        results = []
        if tasks:
            task_results = {}
            results_list = [None] * len(tasks)
            
            pending_tasks = {idx: info for idx, info in enumerate(tasks)}
            in_progress = {} # Maps future -> task index
            
            logger.info(f"Planner identified {len(tasks)} tasks. Executing with max_workers={self.max_workers}...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                while pending_tasks or in_progress:
                    # Find and schedule unblocked tasks
                    ready_to_schedule = []
                    for idx, info in list(pending_tasks.items()):
                        depends_on = info.get("depends_on", [])
                        if all(dep in task_results for dep in depends_on):
                            ready_to_schedule.append((idx, info))
                    
                    for idx, info in ready_to_schedule:
                        del pending_tasks[idx]
                        logger.info(f"Starting task {idx}: {info.get('task')}")
                        future = executor.submit(self._execute_single_task, info, task_results)
                        in_progress[future] = idx
                    
                    # Prevent infinite wait if dependencies are malformed
                    if not in_progress and pending_tasks:
                        logger.error("Deadlock detected: Tasks have unresolvable dependencies.")
                        raise RuntimeError("Deadlock detected: Tasks have unresolvable dependencies.")
                        
                    # Wait for any currently running task to complete
                    done, _ = concurrent.futures.wait(
                        in_progress.keys(), 
                        return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    
                    # Harvest results
                    for future in done:
                        idx = in_progress.pop(future)
                        res = future.result()
                        logger.info(f"Completed task {idx}: {res.get('task')}")
                        task_results[idx] = res["result"]
                        results_list[idx] = res
            
            results = [r for r in results_list if r is not None]

        if "aggregator" in self.capabilities and results:
            logger.info("Aggregating final results...")
            agg_context = []
            for res in results:
                agg_context.append(f"Task: {res.get('task')}\nSkill: {res.get('skill')}\nResult: {res.get('result')}")
            
            aggregator_input = f"User Request: \"{user_input}\"\n\nContext from previous steps:\n" + "\n\n".join(agg_context)
            final_answer = self.inference(aggregator_input, context_folder=self.capabilities["aggregator"]["path"])
            
            logger.info(f"Final Aggregated Answer:\n{final_answer}")
            results.append({
                "task": "Aggregate results into final answer",
                "skill": "aggregator",
                "result": final_answer
            })
                
        return results
