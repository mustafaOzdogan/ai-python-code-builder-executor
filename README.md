# AI Python Code Builder & Executor

A human-in-the-loop multi-agent workflow built with Microsoft AutoGen that generates Python code, requires explicit human approval before execution, runs code inside an isolated Docker container, and automatically corrects failed executions.

> **Generate → Review → Execute → Fix → Review → Execute**

This project demonstrates how AI-generated code can be combined with human-in-the-loop approval, sandboxed execution, and feedback-driven refinement.

## Why This Project?
AI models can generate useful code, but generated code is not always correct, safe, or ready for execution.

This project explores a controlled workflow where:

* AI generates Python code
* A human explicitly approves execution
* Code runs inside Docker containers
* Execution errors are analyzed
* AI generates corrected versions
* Every correction requires fresh approval

The goal is not simply code generation, but designing an iterative execution workflow with validation and human oversight.

## Key Features

* 🤖 AI-powered Python code generation
* 👨‍💻 Human-in-the-loop approval
* 🐳 Docker-based sandboxed execution
* 🔄 Automatic error correction
* 🛑 Configurable retry limits
* ⚡ Execution success detection
* 🧩 AutoGen `RoundRobinGroupChat` orchestration
* 🔒 Security-aware execution model
* ✅ Unit tests

## Architecture

```text
  User Request
       │
       ▼
 AssistantAgent
       │
       ▼
 approval_func
       │
  ┌────┴────┐
  │         │
Reject     Approve
  │            │
  ▼            ▼
 Stop   CodeExecutorAgent
               │
               ▼
        Docker Container
               │
       ┌───────┴────────┐
       │                │
    Success           Failure
       │                │
       ▼                ▼
     Finish     AssistantAgent
                        │
                        └──────► Generate Fix
```

### Agent Responsibilities

| Component         | Responsibility                   |
| ----------------- | -------------------------------- |
| AssistantAgent    | Generate and correct Python code |
| approval_func     | Human approval                   |
| CodeExecutorAgent | Execute approved code            |
| Docker            | Isolated execution environment   |
| Termination Logic | Control workflow lifecycle       |

## Example Workflow

### User Request
The user provides a Python-related task.

```text
Write a Python function that calculates factorial.
```

### Code Generation
The `AssistantAgent` generates executable Python code.

```python
def factorial(n):
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result

print(factorial(10))
```

### Human Approval
Before execution, the user sees a code preview and explicitly approves or rejects the execution.

Large generated programs are truncated in the CLI preview for readability, while the complete code is passed to the executor.

```text
============================================================
 CODE EXECUTION APPROVAL
============================================================

Generated Python code:
------------------------------------------------------------
number = 10

def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)

print(factorial(number))
------------------------------------------------------------
Total lines: 7

Execute this code?

[y] Yes, execute
[n] No, reject

Your choice:
```

### Code Execution
Approved code is executed by `CodeExecutorAgent` using `DockerCommandLineCodeExecutor`.

The code therefore runs inside a Docker container rather than directly in the application's host Python process.

### Successful Execution

If execution succeeds, the output is shown:

```text
EXECUTOR
------------------------------------------------------------
3628800
```

### Failed execution

If execution fails:

```text
NameError: variable 'number' is not defined
```

The error is returned to `AssistantAgent`.

The assistant generates corrected code.

Human approval is required again.

### Termination
Workflow stops when:

Execution succeeds


* Execution succeeds:
```text
============================================================
                    TERMINATION
============================================================

Code execution completed successfully.
```
* User rejects execution
```text
============================================================
                    TERMINATION
============================================================


```
* Maximum failure count is reached
```text
============================================================
                    TERMINATION
============================================================

Maximum failed execution count reached: 3.
```

## Failure Limit

The workflow allows a maximum of **3 failed executions** by default.

```text
Execution #1 → failed
Execution #2 → failed
Execution #3 → failed
                  │
                  ▼
                STOP
```

Example:

```text
Execution failed (1/3)
Execution failed (2/3)
Execution failed (3/3)

============================================================
                    TERMINATION
============================================================

Maximum failed execution count reached: 3.
```

This prevents an endless correction loop.

`MAX_TURNS` provides an additional final safety ceiling for the overall AutoGen conversation.

The two limits have different responsibilities:

| Limit                   | Responsibility                    |
| ----------------------- | --------------------------------- |
| `MAX_FAILED_EXECUTIONS` | Workflow/business rule            |
| `MAX_TURNS`             | Overall conversation safety limit |

# Human-in-the-Loop

Human approval is implemented using `CodeExecutorAgent`'s `approval_func`.

```python
executor = CodeExecutorAgent(
    name="executor",
    code_executor=code_executor,
    approval_func=approval_func,
)
```

The approval function receives the code that is about to be executed.

```python
def approval_func(request) -> ApprovalResponse:
    ...
```

The user can explicitly approve or reject:

```text
[y] Yes, execute
[n] No, reject
```

No generated or corrected code is executed without approval.

### Why not `UserProxyAgent`?

`UserProxyAgent` can be used for human interaction in AutoGen, but it is not necessary for this workflow.

The human is not acting as another conversational agent. The human has one specific responsibility:

> Approve or reject code execution.

Therefore, `approval_func` provides a simpler and more precise abstraction.

`UserProxyAgent` would make more sense if the human needed to participate in the conversation itself, for example:

```text
Assistant → asks clarification
              ↓
           Human answer
              ↓
Assistant → continues reasoning
```

This project deliberately keeps human interaction as an **execution approval gate**.

# Why `CodeExecutorAgent` Has No Model Client

The executor is intentionally created without a model client:

```python
executor = CodeExecutorAgent(
    name="executor",
    code_executor=code_executor,
    approval_func=approval_func,
)
```

The responsibilities are deliberately separated:

| Component           | Responsibility               |
| ------------------- | ---------------------------- |
| `AssistantAgent`    | Generate and fix Python code |
| `CodeExecutorAgent` | Approval and code execution  |
| Docker              | Execution isolation          |

The assistant owns all LLM-based reasoning.

The executor owns execution.

Giving the executor its own LLM would duplicate the code-generation responsibility and make the workflow harder to reason about.

# AutoGen 0.7.5 Execution Result Handling

One important implementation detail is related to how `CodeExecutorAgent` behaves when it is used **without a model client**.

In this configuration, AutoGen 0.7.5 executes the received code directly and exposes the execution result through an executor `TextMessage`.

Therefore, this project does not rely on:

```python
CodeExecutionEvent.result.exit_code
```

for execution failure detection.

Instead, the project contains a small adapter:

```python
def is_executor_error(message) -> bool:
    ...
```

The adapter identifies execution failures from the executor's output message.

### Why use this approach?

The current workflow only needs to distinguish:

```text
Executor result
      │
      ├── success → STOP
      │
      └── failure → Assistant fixes code
```

Introducing a custom executor solely to expose a structured exit code would add complexity without providing significant value for the current use case.

This is a deliberate architectural trade-off.

### Future extension

A more advanced implementation could use richer execution events and route failures based on their type:

```text
exit code 0
    → success

exit code 1
    → debugging / correction

exit code 137
    → resource / container failure

timeout
    → retry or abort
```

That would justify introducing a custom executor or a more event-driven execution architecture.

# Termination Strategy

The project uses two termination conditions.

### Successful execution

```python
successful_execution = FunctionalTermination(
    is_executor_result_successful
)
```

The workflow terminates when the latest executor result represents a successful execution.

### Maximum failures

```python
max_failures_termination = MaxExecutionFailuresTermination(
    max_failed_executions=MAX_FAILED_EXECUTIONS
)
```

The custom termination condition counts failed executions.

The conditions are combined:

```python
termination = (
    successful_execution
    | max_failures_termination
)
```

Conceptually:

```text
             ┌── successful execution ──→ STOP
             │
Execution ───┤
             │
             └── failure ──→ retry
                              │
                              ├── failure
                              ├── failure
                              └── maximum → STOP
```

# Security Model

The project deliberately separates **code generation** from **code execution**.

```text
AI-generated Python
        │
        ▼
Human approval
        │
        ▼
Docker container
        │
        ▼
Execution
```

Docker provides an additional isolation boundary.

However, Docker execution should **not** be considered an absolute security guarantee.

Human approval is a workflow control, not a substitute for sandboxing.

This project is intended as a development and demonstration project, not as a hardened production sandbox for arbitrary hostile code.

For production use, additional controls may be required, such as:

* container resource limits
* network restrictions
* read-only filesystems
* non-root execution
* CPU and memory limits
* execution timeouts
* seccomp/AppArmor policies
* dedicated sandbox infrastructure

# Project Structure

```text
ai-python-code-builder-executor/
│
├── app/
│   ├── code_builder.py
│   ├── config.py
│   ├── prompts.py
│   └── termination_conditions.py
│
├── tests/
│   └── test_termination_conditions.py
│
├── working/
│   └── .gitkeep
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

### `app/code_builder.py`

Main application entry point.

Responsible for:

* model configuration
* agent creation
* Docker executor creation
* human approval
* team configuration
* streaming workflow execution

### `app/config.py`

Loads configuration from `.env`.

### `app/prompts.py`

Contains the system prompt used by the `AssistantAgent`.

### `app/termination_conditions.py`

Contains:

* executor error detection
* successful execution detection
* maximum failed-execution termination

### `tests/`

Contains unit tests for the custom termination logic.

### `working/`

Working directory used by the Docker code executor.

# Configuration

Configuration is stored in `.env`.

Example:

```env
OPENAI_API_KEY=

OPENAI_MODEL=gpt-4o-mini
CODE_WORK_DIR=working

CODE_PREVIEW_MAX_LINES=50
CODE_PREVIEW_HEAD_LINES=25
CODE_PREVIEW_TAIL_LINES=25

MAX_FAILED_EXECUTIONS=3
MAX_TURNS=12
```

Do not commit `.env` to Git.

Use `.env.example` as the template for other developers.

# Requirements

* Python 3.14+
* Docker Desktop
* OpenAI API key
* Windows, macOS, or Linux

The project currently uses:

```text
autogen-agentchat==0.7.5
autogen-ext[openai,docker]==0.7.5
python-dotenv==1.2.3
```

# Installation

Clone the repository:

```bash
git clone https://github.com/mustafaOzdogan/ai-python-code-builder-executor.git
cd ai-python-code-builder-executor
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create `.env` from the example:

```powershell
Copy-Item .env.example .env
```

Add your OpenAI API key:

```env
OPENAI_API_KEY=your_api_key
```

Make sure Docker Desktop is running.

Verify Docker:

```powershell
docker run hello-world
```

# Running the Application

From the project root:

```powershell
python .\app\code_builder.py
```

The application starts with:

```text
============================================================
              AI PYTHON CODE BUILDER
============================================================

What Python program would you like to build?
>
```

Enter a natural-language Python task.

For example:

```text
Create a Python program that calculates the factorial of 10.
```

The assistant generates the code and waits for human approval before execution.

# Testing

Run the test suite with:

```powershell
python -m pytest
```

The tests cover the custom execution-failure termination logic.

# Example: Successful Correction

A typical workflow looks like:

```text
User
 │
 │ "Calculate factorial of 10"
 ▼
Assistant
 │
 │ Generates code
 ▼
Human approval
 │
 │ Approve
 ▼
Docker
 │
 │ NameError
 ▼
Assistant
 │
 │ Fixes code
 ▼
Human approval
 │
 │ Approve
 ▼
Docker
 │
 │ 3628800
 ▼
STOP
```

The important property is that the corrected code requires **another approval**.

# Design Principles

### 1. One responsibility per agent

`AssistantAgent` generates and fixes code.

`CodeExecutorAgent` handles approval and execution.

### 2. Human approval before every execution

No generated or corrected code is automatically executed.

### 3. Execution is isolated

Approved code runs inside Docker rather than directly in the application's host Python process.

### 4. Explicit termination

The workflow stops after:

* successful execution
* maximum failed executions
* the final `MAX_TURNS` safety limit

### 5. Minimal abstraction

The project avoids introducing additional agents or custom infrastructure unless the current requirements actually need them.

# Future Improvements

Possible future extensions include:

* automated unit-test generation
* test execution before final success
* richer execution-event handling
* timeout detection
* Docker resource limits
* network isolation
* execution history
* persistent conversation state
* Web UI instead of CLI
* streaming code diffs between attempts
* structured execution results
* specialized debugging agents
* static analysis before execution

A possible future architecture could be:

```text
                    User
                      │
                      ▼
                Code Generator
                      │
                      ▼
                Human Approval
                      │
                      ▼
                Code Executor
                      │
             ┌────────┴────────┐
             │                 │
          success            failure
             │                 │
             ▼                 ▼
          Testing          Debugger
             │                 │
             └────────┬────────┘
                      │
                      ▼
                  Human Review
```

## Limitations

* The workflow currently supports Python only
* Human approval is required
* Generated code quality depends on the LLM
* Docker is not a complete security boundary

## Future Improvements

* Support multiple programming languages
* Add execution history
* Add code quality evaluation
* Support multiple LLM providers
* Add web interface
* Add advanced sandboxing

# License

This project is licensed under the MIT License.
