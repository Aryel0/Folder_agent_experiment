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

    def __init__(self, allowed_directories: list[str] | None = None):
        """Initialize the ToolRegistry with empty data structures.
        
        self.tools maintains a flat mapping from tool name to the BaseTool instance.
        self.modules maintains a hierarchical mapping grouped by the source module name.
        """
        self.tools = {}       # flat: tool_name -> BaseTool instance
        self.modules = {}     # grouped: module_name -> {tool_name: BaseTool instance}
        self.allowed_directories = allowed_directories

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
                    instance.allowed_directories = self.allowed_directories
                    self.tools[instance.name] = instance
                    self.modules.setdefault(mod_name, {})[instance.name] = instance
                    logger.debug(f"Registered tool: {instance.name} from {mod_name}")
        logger.info(f"Discovered {len(self.tools)} tools from {registry_dir}")

    def get_ollama_tools(self, names):
        """Build Ollama-compatible tool definitions for tools or modules specified in names."""
        tools = []
        for name in names:
            if name in self.modules:
                for tool_name, tool in self.modules[name].items():
                    tools.append(tool.to_ollama_tool())
            elif name in self.tools:
                tools.append(self.tools[name].to_ollama_tool())
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
        """Run ollama.chat with Ollama-native tool calling support, with fallback."""
        ollama_tools = self.get_ollama_tools(tool_names)
        
        try:
            # Try native tool calling first
            return self._chat_with_native_tools(model, prompt, ollama_tools, output_type)
        except Exception as e:
            e_str = str(e)
            if "does not support tools" in e_str or "400" in e_str or "not support" in e_str:
                logger.info(f"Model '{model}' does not support native tools. Falling back to prompt-based tool calling...")
                return self._chat_with_fallback_tools(model, prompt, ollama_tools, output_type)
            else:
                logger.error(f"Native tool chat failed: {e}. Falling back to prompt-based tool calling...")
                return self._chat_with_fallback_tools(model, prompt, ollama_tools, output_type)

    def _chat_with_native_tools(self, model, prompt, ollama_tools, output_type=None):
        messages = [{"role": "user", "content": prompt}]
        context_manager = Context_Manager(max_tokens=4000, model_name=model)

        max_rounds = 5
        content = ""
        for _ in range(max_rounds):
            messages = context_manager.get_context(messages)
            
            kwargs = {"model": model, "messages": messages, "tools": ollama_tools}
            if output_type == "json":
                kwargs["format"] = "json"

            response = ollama.chat(**kwargs)
            msg = response["message"] if isinstance(response, dict) else response.message
            content = (msg.get("content", "") if isinstance(msg, dict) else msg.content) or ""
            tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else msg.tool_calls

            if not tool_calls:
                return content

            messages.append(msg if isinstance(msg, dict) else {"role": "assistant", "content": content, "tool_calls": tool_calls})

            results = self.execute_tool_calls(tool_calls)
            for r in results:
                preview = r["result"][:200].replace("\n", " ")
                logger.info(f"  [tool:{r['name']}] {preview}")
                messages.append({"role": "tool", "content": r["result"]})

        return content

    def _chat_with_fallback_tools(self, model, prompt, ollama_tools, output_type=None):
        tools_desc = []
        for ot in ollama_tools:
            func = ot["function"]
            tools_desc.append(f"- {func['name']}: {func['description']}. Arguments: {json.dumps(func['parameters'])}")
        
        tools_str = "\n".join(tools_desc)
        
        instructions = f"""You are an agent with access to the following tools:
{tools_str}

CRITICAL RULES:
1. To call a tool, you MUST respond ONLY with a JSON object of this exact format:
{{
  "tool_call": {{
    "name": "tool_name",
    "arguments": {{
       "arg1": "value1",
       ...
    }}
  }}
}}

2. If you have finished calling tools and want to give your final response to the user, you MUST respond ONLY with a JSON object of this exact format:
{{
  "final_response": "your detailed final answer text here"
}}

All of your responses MUST be valid JSON matching one of the two formats above."""

        messages = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt}
        ]
        context_manager = Context_Manager(max_tokens=4000, model_name=model)
        
        max_rounds = 5
        for _ in range(max_rounds):
            messages = context_manager.get_context(messages)
            
            response = ollama.chat(
                model=model,
                messages=messages,
                format="json"
            )
            msg = response["message"] if isinstance(response, dict) else response.message
            content = (msg.get("content", "") if isinstance(msg, dict) else msg.content) or ""
            
            try:
                parsed = json.loads(content)
            except Exception as e:
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Invalid JSON response: {e}. Please respond with either a 'tool_call' or 'final_response' JSON object."})
                continue
                
            if "tool_call" in parsed:
                tc = parsed["tool_call"]
                name = tc.get("name")
                args = tc.get("arguments", {})
                
                tool_calls = [{"function": {"name": name, "arguments": args}}]
                results = self.execute_tool_calls(tool_calls)
                
                messages.append({"role": "assistant", "content": json.dumps(parsed)})
                messages.append({"role": "user", "content": f"Tool '{name}' returned result: {results[0]['result']}"})
            elif "final_response" in parsed:
                return parsed["final_response"]
            else:
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "Your response must contain either 'tool_call' or 'final_response'. Please try again."})
                
        return content