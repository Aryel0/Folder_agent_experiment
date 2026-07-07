import importlib.util
import inspect
import json
# pyrefly: ignore [missing-import]
import ollama
from pathlib import Path
from utils.logger import get_logger
from core.memory.context import Context_Manager
from core.tools.base import BaseTool

logger = get_logger(__name__)


class ToolRegistry:
    """Discovers, registers, and executes BaseTool instances for the agent."""

    def __init__(self):
        """Initialize the ToolRegistry with empty data structures.
        
        self.tools maintains a flat mapping from tool name to the BaseTool instance.
        self.modules maintains a hierarchical mapping grouped by the source module name.
        """
        self.tools = {}       # flat: tool_name -> BaseTool instance
        self.modules = {}     # grouped: module_name -> {tool_name: BaseTool instance}

    def register(self, tool: BaseTool):
        """Manually register a single BaseTool instance.
        
        Args:
            tool (BaseTool): The tool instance to register.
        """
        self.tools[tool.name] = tool

    def get(self, name):
        """Retrieve a registered tool by name.
        
        Args:
            name (str): The identifier name of the registered tool.
            
        Returns:
            BaseTool: The registered tool instance.
            
        Raises:
            KeyError: If the tool name is not registered.
        """
        return self.tools[name]

    def run(self, name, **kwargs):
        """Execute a registered tool with the provided keyword arguments.
        
        Validates arguments against the tool's schema before execution.
        
        Args:
            name (str): The identifier name of the tool to execute.
            **kwargs: The keyword arguments to pass to the tool.
            
        Returns:
            str: The result returned by the executed tool.
        """
        tool = self.tools[name]
        validated = tool.validate(kwargs)
        return tool.run(**validated)

    def auto_discover(self, registry_dir):
        """Scan a directory of .py files and register all BaseTool subclasses."""
        registry_path = Path(registry_dir)
        if not registry_path.is_dir():
            return

        for py_file in sorted(registry_path.glob("*.py")):
            mod_name = py_file.stem
            spec = importlib.util.spec_from_file_location(mod_name, py_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            for attr_name, obj in inspect.getmembers(mod, inspect.isclass):
                # Only register classes that are subclasses of BaseTool
                # and are not BaseTool itself
                if issubclass(obj, BaseTool) and obj is not BaseTool:
                    instance = obj()
                    self.tools[instance.name] = instance
                    self.modules.setdefault(mod_name, {})[instance.name] = instance
                    logger.debug(f"Registered tool: {instance.name} from {mod_name}")
        logger.info(f"Discovered {len(self.tools)} tools from {registry_dir}")

    def get_ollama_tools(self, module_names):
        """Build Ollama-compatible tool definitions for tools in the given modules."""
        tools = []
        for mod_name in module_names:
            for tool_name, tool in self.modules.get(mod_name, {}).items():
                tools.append(tool.to_ollama_tool())
        return tools

    def execute_tool_calls(self, tool_calls):
        """Execute a list of tool calls from Ollama's response and return results.
        
        Each tool call's arguments are validated against the tool's schema
        before execution. Validation errors are returned as clear messages
        that the LLM can use to self-correct.
        """
        results = []
        for tc in tool_calls:
            # Support both dict and object-style tool calls
            if isinstance(tc, dict):
                name = tc["function"]["name"]
                args = tc["function"]["arguments"]
            else:
                name = tc.function.name
                args = tc.function.arguments

            # Arguments may arrive as a JSON string
            if isinstance(args, str):
                args = json.loads(args)

            if name in self.tools:
                tool = self.tools[name]
                try:
                    logger.info(f"Executing tool: {name} with args: {args}")
                    validated_args = tool.validate(args)
                    result = tool.run(**validated_args)
                    logger.debug(f"Tool {name} result: {str(result)[:200]}...")
                except ValueError as e:
                    # Validation error — send back to LLM for self-correction
                    logger.warning(f"Validation error for tool {name}: {e}")
                    result = f"Validation error for {name}: {e}"
                except Exception as e:
                    logger.exception(f"Error executing tool {name}")
                    result = f"Error executing {name}: {e}"
            else:
                logger.warning(f"Attempted to execute unknown tool: {name}")
                result = f"Unknown tool: {name}"
            results.append({"name": name, "result": str(result)})
        return results

    def chat_with_tools(self, model, prompt, tool_names, output_type=None):
        """Run ollama.chat with Ollama-native tool calling support.

        Loops up to max_rounds: each round the model may request tool calls,
        which are executed and fed back as tool messages until the model
        produces a final text response.
        
        Args:
            model (str): The name of the model to use.
            prompt (str): The initial user prompt.
            tool_names (list): A list of tool names the model is permitted to call.
            output_type (str, optional): The expected output type constraint (e.g., 'json').
            
        Returns:
            str: The final textual response from the model after all tool calls complete.
        """
        messages = [{"role": "user", "content": prompt}]
        ollama_tools = self.get_ollama_tools(tool_names)
        context_manager = Context_Manager(max_tokens=4000, model_name=model)

        max_rounds = 5
        content = ""
        for _ in range(max_rounds):
            # Prune or summarize history if it gets too large
            messages = context_manager.get_context(messages)
            
            kwargs = {"model": model, "messages": messages, "tools": ollama_tools}
            if output_type == "json":
                kwargs["format"] = "json"

            response = ollama.chat(**kwargs)
            # Support both dict and object-style responses
            msg = response["message"] if isinstance(response, dict) else response.message
            content = (msg.get("content", "") if isinstance(msg, dict) else msg.content) or ""
            tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else msg.tool_calls

            if not tool_calls:
                return content

            # Add assistant message to conversation history
            messages.append(msg if isinstance(msg, dict) else {"role": "assistant", "content": content, "tool_calls": tool_calls})

            # Execute each tool call and feed results back
            results = self.execute_tool_calls(tool_calls)
            for r in results:
                preview = r["result"][:200].replace("\n", " ")
                logger.info(f"  [tool:{r['name']}] {preview}")
                messages.append({"role": "tool", "content": r["result"]})

        return content