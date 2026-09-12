from __future__ import annotations
import json
import yaml
import os
import platform
# pyrefly: ignore [missing-import]
import ollama
from pathlib import Path
from core.tools.executor import ToolRegistry
from core.memory import Memory
from utils.logger import get_logger

logger = get_logger(__name__)

class FolderAgent:
    """A directory-based agent that orchestrates LLM tasks using registered capabilities.
    
    The FolderAgent dynamically loads capabilities (skills) from directories, 
    constructs prompts by merging context (configs, tools, examples, memory), 
    and interacts with an Ollama model to generate plans and execute tasks.
    """

    def __init__(self, model_name: str, memory_root: str = "core/memory", capabilities_root: str = "capabilities", max_workers: int = 1, allowed_directories: list[str] | None = None):
        """Initialize the FolderAgent with a specific model and configuration.
        
        Args:
            model_name (str): The name of the Ollama model to use for inference.
            memory_root (str): The root directory path for the memory stores (default: "core/memory").
            capabilities_root (str): The root directory to scan for capabilities (default: "capabilities").
            max_workers (int): Maximum number of parallel workers for task execution (default: 1).
            allowed_directories (list[str] | None): A list of directories the agent is allowed to modify (default: None for unrestricted).
        """
        self.model = model_name
        self.os_name = platform.system()
        self.workspace_dir = os.getcwd()
        self.registry = ToolRegistry(allowed_directories)
        self.registry.auto_discover("core/tools/registery")
        self.memory = Memory(storage_root=memory_root)
        self.max_workers = max_workers
        self.context = {}
        self.capabilities: dict[str, dict] = {}
        self.register_capabilities(capabilities_root)

    def register_capabilities(self, root_dir: str = "capabilities"):
        """Scan root_dir once to discover and register all available capabilities.
        
        A valid capability is any subdirectory containing a 'manifest.yaml' file.
        The name of the capability is derived from the directory name (lowercased).
        
        Args:
            root_dir (str): The root directory to search for capabilities (default: ".").
        """
        root = Path(root_dir)
        for path in root.iterdir():
            if path.is_dir() and (path / "manifest.yaml").exists():
                cap_name = path.name.lower()
                try:
                    manifest_data = yaml.safe_load((path / "manifest.yaml").read_text())
                    self.capabilities[cap_name] = {
                        "path": path,
                        "manifest": manifest_data,
                        "context": self._parse_folder(path)
                    }
                except yaml.YAMLError as e:
                    logger.warning(f"Failed to load manifest for capability '{cap_name}': {e}. Capability rejected.")

    def _parse_folder(self, folder: Path) -> dict:
        """Internal helper to parse a capability folder into a context dictionary once."""
        context = {}
        # prompt (required file)
        context["prompt"] = (folder / "prompt.md").read_text() if (folder / "prompt.md").exists() else ""
        
        # config (optional file)
        config_path = folder / "config.yaml"
        context["config"] = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}

        # manifest (required file)
        manifest_path = folder / "manifest.yaml"
        context["manifest"] = yaml.safe_load(manifest_path.read_text()) if manifest_path.exists() else {}

        # tools (optional file)
        tool_path = folder / "tools.json"
        context["tools"] = json.loads(tool_path.read_text()) if tool_path.exists() else {}

        # examples (optional folder)
        examples_path = folder / "examples"
        if not examples_path.exists():
            examples_path = folder / "example"
        context["examples"] = []

        if examples_path.exists():
            for f in sorted(examples_path.iterdir()):
                if f.is_file():
                    ext = f.suffix
                    if ext in [".md", ".txt"]:
                        context["examples"].append(f.read_text())
                    if ext in [".json"]:
                        context["examples"].append(json.dumps(json.loads(f.read_text()), indent=2))

        context["memory"] = []
        return context

    def load_folder(self, folder_path: str):
        """Load the folder context item for the agent to use as a capability.
        
        This now retrieves the pre-parsed context from memory to avoid redundant disk I/O.
        
        Args:
            folder_path (str): The path to the capability folder.
            
        Returns:
            dict: The populated context dictionary for the given capability.
        """
        folder_path_obj = Path(folder_path)
        
        # Fast path: retrieve from cached capabilities
        for cap in self.capabilities.values():
            if cap["path"] == folder_path_obj:
                self.context = cap["context"]
                return self.context
                
        # Fallback for dynamic/unregistered folders
        self.context = self._parse_folder(folder_path_obj)
        return self.context

    def build_prompt(self, context_folder: Path, user_input: str) -> str:
        """Build the prompt for the model based on the folder context item and user input.
        
        Combines the system prompt, configuration, available tools, examples, 
        and conversational memory into a single structured string for the LLM.
        
        Args:
            context_folder (Path): The path to the capability folder being executed.
            user_input (str): The raw text input from the user or task description.
            
        Returns:
            str: The fully constructed prompt string ready for inference.
        """
        parts = []

        parts.append("SYSTEM:")
        system_prompt = self.context.get("prompt", "")
        system_prompt += f"\n\nEnvironment Context:\n- Operating System: {self.os_name}\n- Current Working Directory: {self.workspace_dir}\n"
        
        # If the capability is the planner, dynamically append the list of available skills and their manifests
        if context_folder.name.lower() == "planner" and self.capabilities:
            # Tagline Optimization: Only send taglines to the planner to save tokens
            taglines_only = {
                k: v.get("manifest", {}).get("tagline", v.get("manifest", {}).get("description", ""))
                for k, v in self.capabilities.items()
            }
            system_prompt += f"\n\nAvailable capability/skill options you can use for tasks:\n{json.dumps(taglines_only, indent=2)}"
        parts.append(system_prompt)

        if self.context["config"]:
            parts.append("\nCONFIG:")
            parts.append(str(self.context["config"]))

        if self.context["tools"]:
            parts.append("\nTOOLS:")
            resolved_tool_names = self.context["tools"].get("tools", [])
            ollama_tools = self.registry.get_ollama_tools(resolved_tool_names)
            tools_info = []
            for ot in ollama_tools:
                func = ot["function"]
                tools_info.append({
                    "name": func["name"],
                    "description": func["description"],
                    "parameters": func["parameters"]
                })
            parts.append(json.dumps(tools_info, indent=2))

        if self.context["examples"]:
            parts.append("\nEXAMPLES:")
            parts.extend(self.context["examples"])

        # Inject memory only if the capability opts in (default: true)
        if self.context["config"].get("use_memory", True):
            memory_context = self.memory.recall(user_input)
            if memory_context.strip():
                parts.append("\nMEMORY:")
                parts.append(memory_context)

        parts.append("\nRULES FOR EXECUTION:")
        parts.append("- You MUST use the provided tools to interact with the system if an action is required.")
        parts.append("- NEVER assume a tool call was successful unless you receive a confirmation message.")
        parts.append("- If a tool call fails (e.g. returns an Error), you MUST report the failure to the user and NOT hallucinate a successful outcome.")

        parts.append("\nUSER:")
        parts.append(user_input)

        return "\n\n".join(parts)
    

    def post_process(self, context, output):
        """Post-process the raw output from the LLM based on capability configuration.
        
        If the configuration specifies an 'output_type' of 'json', it attempts 
        to extract and parse the first valid JSON object or array from the output.
        
        Args:
            context (dict): The loaded capability context containing the configuration.
            output (str): The raw text response generated by the LLM.
            
        Returns:
            str | dict | list: The post-processed output, which may be a parsed JSON structure or raw text.
        """
        output_type = context["config"].get("output_type")

        if output_type == "json":
            return json.loads(self._extract_json(output))

        return output

    @staticmethod
    def _extract_json(text):
        """Extract the first complete JSON object or array from text.

        Uses a bracket-depth scanner to handle nested structures,
        strings with escaped characters, and surrounding prose.
        """
        for i, ch in enumerate(text):
            if ch not in ('{', '['):
                continue
            depth = 0
            in_string = False
            escape_next = False
            for j in range(i, len(text)):
                c = text[j]
                if escape_next:
                    escape_next = False
                    continue
                if c == '\\' and in_string:
                    escape_next = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c in ('{', '['):
                    depth += 1
                elif c in ('}', ']'):
                    depth -= 1
                    if depth == 0:
                        return text[i:j+1]
        return text
    
    def inference(self, user_input: str, context_folder: Path | str):
        """Run inference on the model using a specific capability folder.
        
        This method acts as the entry point for executing a capability. It loads the 
        folder, records the prompt in memory, dispatches to either the streaming 
        generator or the tool-calling chat engine based on whether tools are present, 
        and finally processes the output.
        
        Args:
            user_input (str): The user's query or task instruction.
            context_folder (Path | str): The path to the capability directory.
            
        Returns:
            str | dict | list: The generated output from the model, post-processed.
        """
        context_folder = Path(context_folder)
        context = self.load_folder(context_folder)

        # Record the user turn in short-term memory
        self.memory.add("short_term", user_input, {"role": "user"})

        prompt = self.build_prompt(context_folder, user_input)

        output_type = context["config"].get("output_type")
        tool_names = context.get("tools", {}).get("tools", [])

        if tool_names:
            output = self.registry.chat_with_tools(self.model, prompt, tool_names, output_type)
            if output:
                logger.info(output)
        else:
            output = self._stream_generate(prompt, output_type)

        # Record the agent turn in short-term memory
        self.memory.add("short_term", output, {"role": "agent"})

        return self.post_process(context, output)

    def _stream_generate(self, prompt, output_type=None):
        """Run ollama.generate with streaming output to the console.
        
        Args:
            prompt (str): The final constructed prompt to send to the model.
            output_type (str, optional): The expected output type. If 'json', 
                the model is constrained to generate valid JSON format.
                
        Returns:
            str: The concatenated string of all output chunks generated by the model.
        """
        kwargs = {"model": self.model, "prompt": prompt, "stream": True}
        if output_type == "json":
            kwargs["format"] = "json"

        response = ollama.generate(**kwargs)
        chunks = []
        for chunk in response:
            text = chunk.get("response", "")
            print(text, end="", flush=True)
            chunks.append(text)
        print()
        return "".join(chunks)

    def _route_request(self, user_input: str) -> str:
        """Route the user's request to the appropriate capability or the planner.
        
        Args:
            user_input (str): The raw text input from the user.
            
        Returns:
            str: The name of the capability to use, or "planner" if complex.
        """
        logger.info("Routing user request...")
        
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
            response = ollama.generate(
                model=self.model,
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
            logger.error(f"Router failed: {e}. Defaulting to planner.")
            return "planner"

    def _execute_single_task(self, task_info: dict, task_results: dict) -> dict:
        """Execute a single task node derived from the planner's dependency graph.
        
        Aggregates context from prerequisite tasks and dispatches the execution to 
        the designated skill/capability.
        
        Args:
            task_info (dict): The task specification containing 'skill', 'task', and 'depends_on'.
            task_results (dict): A dictionary mapping task indices to their completed results.
            
        Returns:
            dict: The result payload containing the 'task', 'skill', and raw 'result' text.
        """
        skill = task_info.get("skill", "").lower()
        task_desc = task_info.get("task", "")
        depends_on = task_info.get("depends_on", [])
        
        # Gather context from dependencies into a precision Scratchpad
        dep_context = ""
        if depends_on:
            dep_context_parts = []
            for dep_idx in depends_on:
                if dep_idx in task_results:
                    raw_result = str(task_results[dep_idx])
                    # Truncation safeguard for massive outputs
                    if len(raw_result) > 2000:
                        raw_result = raw_result[:2000] + "\n...[TRUNCATED: Result exceeded 2000 characters. If this is code, refer to the actual written file on disk.]"
                    dep_context_parts.append(f"[Task {dep_idx} Output]:\n{raw_result}")
            
            if dep_context_parts:
                dep_context = "\n\n".join(dep_context_parts)
        
        # Build prompt for the task execution
        full_task_input = task_desc
        if dep_context:
            full_task_input = f"{task_desc}\n\n=== SCRATCHPAD CONTEXT (From Required Dependencies) ===\n{dep_context}\n========================================================\n"
        
        # Execute using the appropriate capability
        if skill in self.capabilities:
            output = self.inference(full_task_input, context_folder=self.capabilities[skill]["path"])
        else:
            # Fallback: direct generation without capability context
            output = self._stream_generate(full_task_input)
        
        return {
            "task": task_desc,
            "skill": skill,
            "result": output
        }

    def execute(self, user_input: str) -> list[dict]:
        """Execute a user request by routing it or planning it if it's complex.
        
        This method uses a router to determine if a single capability can handle the request.
        If it's complex, it invokes the 'planner' capability to decompose the request into a 
        dependency graph of sub-tasks. It then executes each task one by one.
        
        Args:
            user_input (str): The overall goal or instruction from the user.
            
        Returns:
            list[dict]: A chronologically ordered list of task execution results.
            
        Raises:
            ValueError: If the 'planner' capability is not found.
        """
        if "planner" not in self.capabilities:
            logger.error("Planner capability not registered.")
            raise ValueError("Planner capability not registered.")

        # Route the request
        selected_capability = self._route_request(user_input)
        
        if selected_capability != "planner":
            logger.info(f"Task is simple. Bypassing planner and executing directly with {selected_capability}.")
            output = self.inference(user_input, context_folder=self.capabilities[selected_capability]["path"])
            return [{
                "task": user_input,
                "skill": selected_capability,
                "result": output
            }]

        max_retries = 3
        attempt = 0
        tasks = None
        error_context = ""

        while attempt < max_retries:
            logger.info(f"Consulting planner to break down the request (Attempt {attempt + 1}/{max_retries})...")
            
            # If there's an error from a previous attempt, append it to the user input
            current_input = user_input
            if error_context:
                current_input += f"\n\nERROR FROM PREVIOUS ATTEMPT:\n{error_context}\nPlease correct your plan."
                
            # 1. Run inference on the planner to decompose the task
            plan = self.inference(current_input, context_folder=self.capabilities["planner"]["path"])
            
            # Normalize: accept both "tasks" and "steps" as the plan key
            if isinstance(plan, dict):
                tasks = plan.get("tasks") or plan.get("steps")
                
            if not tasks:
                error_context = "The plan did not contain a 'tasks' array."
                attempt += 1
                continue
                
            # Validate capabilities
            invalid_skills = []
            for t in tasks:
                skill = t.get("skill")
                if skill and skill not in self.capabilities:
                    invalid_skills.append(skill)
                    
            if invalid_skills:
                error_context = f"You used unknown capabilities: {', '.join(invalid_skills)}. Available capabilities are: {list(self.capabilities.keys())}. Review the provided manifests. You MUST use one of the existing capabilities to accomplish this step. Only if NO existing capability can possibly cover the use case should you fail the plan."
                logger.warning(error_context)
                attempt += 1
                tasks = None  # Reset tasks so we loop again
            else:
                # Validation passed
                break

        if not tasks:
            raise ValueError("Planner failed to generate a valid plan with known capabilities after maximum retries. Consider creating a new capability for your specific needs.")

        results = []
        if tasks:
            task_results = {}
            
            logger.info(f"Planner identified {len(tasks)} tasks. Executing sequentially...")
            
            for idx, info in enumerate(tasks):
                logger.info(f"Starting task {idx}: {info.get('task')}")
                res = self._execute_single_task(info, task_results)
                logger.info(f"Completed task {idx}: {res.get('task')}")
                task_results[idx] = res["result"]
                results.append(res)
                
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