# AI Python Code Builder & Executor

A human-in-the-loop Python code generation and execution workflow built with **Microsoft AutoGen**, **OpenAI**, and **Docker**.

The user describes a Python task in natural language. An AI assistant generates the Python code, the user reviews and approves it, and the approved code is executed inside an isolated Docker container.

If execution fails, the assistant analyzes the execution error and generates a corrected version. **Every new or corrected code version requires fresh human approval before execution.**

---

## Architecture

```text
                         User
                           │
                           │ Natural-language task
                           ▼
                  ┌──────────────────┐
                  │  AssistantAgent  │
                  │                  │
                  │ Generate Python  │
                  │ Fix Python code  │
                  └────────┬─────────┘
                           │
                           │ Generated code
                           ▼
                  ┌──────────────────┐
                  │   approval_func  │
                  │                  │
                  │ Human review     │
                  │ [y] Approve      │
                  │ [n] Reject       │
                  └────────┬─────────┘
                           │
                     approved
                           │
                           ▼
                  ┌──────────────────┐
                  │ CodeExecutorAgent│
                  │                  │
                  │ approval gate    │
                  │ + Docker         │
                  └────────┬─────────┘
                           │
                           ▼
                    Docker Container
                           │
                  ┌────────┴─────────┐
                  │                  │
               success             error
                  │                  │
                  ▼                  ▼
                STOP          AssistantAgent
                                     │
                                     │ corrected code
                                     ▼
                              approval_func()
```

The workflow is implemented using `RoundRobinGroupChat`.

---

## Workflow

### 1. User provides a task

For example:

```text
Calculate the factorial of 10 and print the result.
```

### 2. Assistant generates Python code

The `AssistantAgent` generates executable Python code.

```python
number = 10

def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)

print(factorial(number))
```

### 3. Human reviews the code

Before execution, the complete code is available to the executor, while the CLI shows a readable preview.

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

The human must explicitly approve the execution.

### 4. Code executes inside Docker

Approved code is executed by `CodeExecutorAgent` using `DockerCommandLineCodeExecutor`.

The Python process therefore does not execute directly on the host machine.

### 5. Successful execution

If execution succeeds, the workflow terminates.

```text
EXECUTOR
------------------------------------------------------------
3628800

============================================================
                    TERMINATION
============================================================

Code execution completed successfully.
```

### 6. Failed execution

If execution fails, the error is returned to the assistant.

For example:

```text
NameError: name 'number' is not defined
```

The assistant analyzes the error and generates corrected code.

The corrected code is **not automatically executed**.

It goes through the human approval step again:

```text
Assistant
   │
   ▼
Corrected code
   │
   ▼
Human approval
   │
   ▼
Docker execution
```

This prevents an AI-generated correction from being executed without human review.

---

## Failure Limit

The workflow allows a maximum of **3 failed executions**.

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

This protects the workflow from entering an endless correction loop.

`MAX_TURNS` is also configured as a final workflow safety ceiling.

These two limits have different responsibilities:

* `MAX_FAILED_EXECUTIONS` → business/workflow rule
* `MAX_TURNS` → final conversation safety limit

---

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

The user can either:

```text
[y] Yes, execute
[n] No, reject
```

The approval decision is explicit.

### Why not `UserProxyAgent`?

`UserProxyAgent` can be used for human interaction in AutoGen, but it is not necessary for this workflow.

The human is not acting as another conversational agent.

The human has one specific responsibility:

> Approve or reject code execution.

Therefore, `approval_func` provides a simpler and more precise abstraction for this use case.

`UserProxyAgent` would make more sense if the human needed to participate in the conversation itself, for example:

```text
Assistant → asks clarification
             ↓
          Human answer
             ↓
Assistant → continues reasoning
```

This project deliberately keeps human interaction as an **execution approval gate**.

---

# Why `CodeExecutorAgent` Has No Model Client

The executor is intentionally created without a model client:

```python
executor = CodeExecutorAgent(
    name="executor",
    code_executor=code_executor,
    approval_func=approval_func,
)
```

The `AssistantAgent` is responsible for:

* generating code
* analyzing execution errors
* fixing code

The `CodeExecutorAgent` is responsible for:

* receiving code
* requesting human approval
* executing approved code
* returning the execution result

This creates a clear separation of responsibilities:

```text
AssistantAgent
    │
    ├── Generate
    └── Fix
         │
         ▼
CodeExecutorAgent
    │
    ├── Approve
    └── Execute
         │
         ▼
      Docker
```

Giving the executor its own LLM would duplicate the code-generation responsibility and make the workflow harder to reason about.

---

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

The adapter identifies executor failures from the executor's output message.

This is intentionally kept small.

The project does not introduce a custom executor simply to expose an exit code because that would add complexity without providing significant value for the current workflow.

### Why this approach?

The current workflow only needs to distinguish:

```text
executor result
      │
      ├── success → STOP
      │
      └── failure → Assistant fixes code
```

It does not currently need sophisticated routing based on individual exit codes.

### Future extension

A more advanced architecture could use richer execution events and route different failures differently:

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

That would be a good reason to introduce a custom executor or a more event-driven architecture.

For this project, the simpler adapter is intentional.

---

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

The two conditions are combined:

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

---

# Security Model

The project deliberately separates **code generation** from **code execution**.

Generated code is not executed directly on the host machine.

Instead:

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

However, Docker execution should not be considered an absolute security guarantee.

The Docker configuration in this project is intended as a development/demo isolation mechanism, not as a hardened production sandbox for arbitrary hostile code.

For production use, additional controls may be required, such as:

* container resource limits
* network restrictions
* read-only filesystems
* restricted mounts
* non-root execution
* CPU/memory limits
* execution timeouts
* seccomp/AppArmor policies
* dedicated sandbox infrastructure

---

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

### `code_builder.py`

Main application entry point.

Responsible for:

* model configuration
* agent creation
* Docker executor creation
* human approval
* team configuration
* streaming workflow execution

### `config.py`

Loads configuration from `.env`.

### `prompts.py`

Contains the system prompt used by the `AssistantAgent`.

### `termination_conditions.py`

Contains:

* executor error detection
* successful execution detection
* maximum failed execution termination

### `tests/`

Contains unit tests for the custom termination logic.

### `working/`

Working directory used by the Docker code executor.

---

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

---

# Requirements

* Python 3.14+
* Docker Desktop
* OpenAI API key
* Windows/macOS/Linux

The project currently uses:

```text
autogen-agentchat==0.7.5
autogen-ext[openai,docker]==0.7.5
python-dotenv==1.2.3
```

---

# Installation

Clone the repository:

```bash
git clone <repository-url>
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

Create `.env`:

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

---

# Running the Application

From the project root:

```powershell
python .\app\code_builder.py
```

The application asks:

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

---

# Example: Successful Correction

A possible workflow:

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

---

# Design Principles

The project follows several simple principles:

### 1. One responsibility per agent

`AssistantAgent` generates and fixes code.

`CodeExecutorAgent` executes code.

### 2. Human approval before every execution

No generated or corrected code is automatically executed.

### 3. Execution is isolated

Code runs inside Docker rather than directly on the host.

### 4. Explicit termination

The workflow stops after:

* successful execution, or
* maximum failed executions, or
* the final `MAX_TURNS` safety limit.

### 5. Minimal abstraction

The project avoids introducing additional agents or custom infrastructure unless the current requirements actually need them.

---

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
* code quality/static analysis before execution

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

---

# License

This project is licensed under the MIT License.
