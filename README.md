# Folder-Based Agent Architecture

The system is organized around **capabilities**, where each folder represents a single, self-contained software component responsible for one task. A capability does not own state, memory, or tool implementations. It simply receives a context, requests services when needed, and returns a result.

Each capability follows a common structure:

```text
capability/

├── manifest.yaml        # Capability metadata and configuration
├── prompt.md            # Core instructions for the capability
├── schema.json          # Input/output contract
├── tool.json            # Declares the tools this capability may request
├── identity.md          # (Optional) Defines the capability's role/personality
├── constraints.md       # (Optional) Additional execution rules
├── examples/
│   ├── example_1.md
│   └── example_2.md
├── templates/           # (Optional) Output templates
│   └── report.md
└── README.md            # (Optional) Documentation for developers
```

## File Responsibilities

### `manifest.yaml`

Contains metadata used by the runtime.

Example:

* Name
* Version
* Description
* Entry prompt
* Optional files
* Tags
* Configuration

The runtime uses this file to discover and load the capability.

---

### `prompt.md`

Contains the primary instructions describing how the capability should solve its task.

---

### `schema.json`

Defines the capability's public interface.

It specifies:

* Expected inputs
* Produced outputs
* Optional state fields
* Validation rules

This allows capabilities to be connected together without hardcoded logic.

---

### `tool.json`

Declares the tools the capability is allowed or expected to use.

The capability never executes tools directly.

Instead it sends a tool request to the Agent Tool Registry, which resolves the request, executes the appropriate implementation through the Tool Executor, and returns the normalized result.

---

### `identity.md` *(optional)*

Provides a specialized role or reasoning style for the capability.

Examples:

* Software Architect
* Security Auditor
* Technical Writer
* Planner

---

### `constraints.md` *(optional)*

Defines permanent execution rules that should always accompany the prompt.

Examples:

* Never modify source code.
* Return JSON only.
* Do not invent missing information.
* Never call external APIs.

---

### `examples/`

Contains few-shot examples illustrating expected behavior.

The runtime may select only the most relevant examples instead of loading every file.

---

### `templates/` *(optional)*

Contains reusable output formats.

Examples:

* Architecture report
* Code review
* Design proposal

---

### `README.md` *(optional)*

Developer documentation describing the capability's purpose, limitations, and intended usage.

---

## Runtime Architecture

Capabilities are intentionally lightweight.

They do not:

* Store memory
* Manage execution state
* Execute tools directly
* Coordinate other capabilities

Instead, they receive a context from the agent runtime and communicate only through requests and responses.

The Folder Agent is responsible for:

* Loading capabilities
* Building prompts
* Managing short-term, long-term, and RAG memory
* Resolving tool requests
* Executing tools through the Tool Executor
* Passing results back to capabilities
* Coordinating execution between capabilities

This separation allows each capability to behave as an independent software module with a single responsibility, while the agent acts as the orchestration layer that manages state, memory, and execution.
