# Folder-Based Agent Architecture

The system is organized around **capabilities**, where each folder represents a single, self-contained software component responsible for one task. A capability does not own state, memory, or tool implementations. It simply receives a context, requests services when needed, and returns a result.

Each capability follows the Claude skills and folder agent structure:

```text
capability/ (or skill/)

├── skill.md                 # Primary skill definition (frontmatter + instructions)
├── manifest.yaml            # Runtime configuration and/or capability metadata
├── reference/               # (Optional) Security checklist, domain knowledge, docs
├── code/ or scripts/        # (Optional) Validation scripts, deterministic helpers
├── assets/                  # (Optional) Templates, examples, artifacts
├── prompt.md                # (Optional / Legacy) Core instructions
├── tools.json               # (Optional / Legacy) Declares requested tools
└── workflow.md              # (Optional) Explicit workflow and contracts
```

## Capability Specification & File Responsibilities

This architecture adopts the **Claude Skills Architecture** for two main reasons:
1. **Ecosystem Compatibility:** Seamlessly import and leverage the massive existing library of skills (e.g. from GitHub, `skill.sh`, or Claude Code).
2. **Developer Simplicity:** Drastically streamline capability definition down to a single primary instruction file (`skill.md`), eliminating redundant files while making the system intuitive to understand and maintain.

---

### `skill.md`

The primary definition of the capability. Combines structured YAML frontmatter metadata with detailed markdown system instructions:

#### Frontmatter Metadata:
* **`name`**: Unique identifier and display name of the skill.
* **`description`**: Concise summary of what the skill does (used for Level 1 Discovery and intelligent routing).
* **`constrains`** (or **`constraints`**): Strict rules and execution boundaries the skill must adhere to.
* **`inputs`**: Expected input parameter names, types, or preconditions.
* **`outputs`**: Expected output formats (e.g. `json`, markdown report) or schema requirements.
* **`tools`**: List of tools required or requested by this skill.
* **`examples`**: Few-shot examples demonstrating proper skill execution and output.

#### Instructions Body:
The Markdown content below the frontmatter serves as the core system instructions defining the role, methodology, workflow, and guidelines for the capability.

---

### `manifest.yaml`

Contains runtime environment specifications, versioning, and schemas:

* **`version`**: Semantic version of the skill (e.g., `1.0.0`).
* **`runtime`**: Runtime environment required (e.g., `python`, `node`, `bash`).
* **`tools_schemas`**: List of schemas or tools registered for this capability.
* **`permision_schemas`** (or **`permission_schemas`**): List of permission schemas and access controls.
* Capability metadata (name, description, tags, config) when not using frontmatter.

The runtime uses this file alongside `skill.md` to discover and configure the capability.

---

### Optional Directories

#### `reference/` (or `references/`, `docs/`)
Domain knowledge, security checklists, architecture references, and detailed documentation.
Implements **Progressive Disclosure**:
* **Level 1 (Discovery):** Invisible during discovery to conserve tokens.
* **Level 2 (Selection):** Cataloged in the capability context upon selection.
* **Level 3 (On-Demand):** Lazily loaded on-demand via `load_capability_reference` only when explicitly requested.

#### `code/` (or `scripts/`)
Deterministic validation scripts, AST analyzers, and helper routines that execute programmatically rather than burning LLM tokens.

#### `assets/`
Reusable output templates, artifact templates, sample datasets, and example files. Automatically exposed in the capability's context.

---

### Legacy Compatibility (Deprecated)

For backwards compatibility with early prototypes, the runtime gracefully supports:
* **`prompt.md`**: Legacy instruction prompt (superseded by `skill.md`).
* **`tools.json`**: Legacy tool declaration list (superseded by `tools` key in `skill.md` or `manifest.yaml`).
* **`workflow.md`**: Legacy workflow document (integrated into `skill.md` workflow section).

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

* Loading capabilities using progressive disclosure (Level 1: Discovery, Level 2: Selection, Level 3: On-Demand References)
* Building prompts incorporating constraints, inputs/outputs contracts, runtime info, and templates
* Managing short-term, long-term, and RAG memory
* Resolving tool requests via the Tool Registry and Executor
* Coordinating execution and multi-step plans via the Planner and Router
* Validating input and output contracts against workflow schemas

This separation allows each capability to behave as an independent software module with a single responsibility, while the agent acts as the orchestration layer that manages state, memory, and execution.

---

## Core Upgrades

The `core/upgrade/` directory contains advanced agent architectures extending the base [FolderAgent](file:///c:/Users/steph/Documents/Lab/experiment801/core/agent.py):

### 1. ParallelFolderAgent ([parallel_agent.py](file:///c:/Users/steph/Documents/Lab/experiment801/core/upgrade/parallel_agent.py))

* **Problem Solved:** Accelerates multi-step plan execution. It parses the dependency graph generated by the planner and executes independent tasks concurrently using a thread pool.
* **Trade-offs:**
  * High risk of hitting API rate limits or saturating LLM backend services.
  * Console outputs from concurrent threads can interlace and become hard to read/debug.
  * Failure handling is complex, requiring orchestration to cancel downstream tasks if a parent branch fails.

### 2. LearningFolderAgent ([learning_agent.py](file:///c:/Users/steph/Documents/Lab/experiment801/core/upgrade/learning_agent.py))

* **Problem Solved:** Integrates self-reflection. Post-execution, the agent uses the LLM to inspect the run's transcript, extract key insights (successful commands, bugs resolved, tool limits), and write them into long-term memory for future runs.
* **Trade-offs:**
  * Adds computational and token overhead with an extra LLM call at the end of every run.
  * May clutter long-term memory with redundant or low-quality lessons if the task was simple.

### 3. DualModelAgent ([dual_model_agent.py](file:///c:/Users/steph/Documents/Lab/experiment801/core/upgrade/dual_model_agent.py))

* **Problem Solved:** Optimizes latency and API costs. It delegates simple routing decisions and background text summarization to a fast, tiny model (e.g. `llama3.2:1b`), reserving the heavy, capable model (e.g. `mistral-nemo:latest`) for primary tasks.
* **Trade-offs:**
  * Tiny models are more prone to parsing errors, hallucinations, and misrouting complex requests.
  * Background summarization by a small model can omit subtle but critical contextual details.


## License

This software is released under a **Proprietary / Read-Only License**.

* **Allowed:** You may read and review the source code for reference, educational, or hosting platform (e.g., GitHub) display purposes.
* **Prohibited:** You may not copy, modify, distribute, sublicense, or run/use the software for any commercial or non-commercial application without express written permission from the copyright owner.

For full terms, please see the [LICENSE](file:///c:/Users/steph/Documents/Lab/experiment801/LICENSE) file.
