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
  ┌────┴───────┐
  │            │
Reject      Approve
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
Create a Python program that calculates the factorial of 10.
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

Code execution was rejected by the user.
```
* Maximum failure count is reached
```text
============================================================
                    TERMINATION
============================================================

Maximum failed execution count reached: 3.
```

## Technology Stack

| Component       | Technology          |
| --------------- | ------------------- |
| Agent Framework | Microsoft AutoGen   |
| Orchestration   | RoundRobinGroupChat |
| LLM             | OpenAI GPT Models   |
| Execution       | Docker              |
| Language        | Python              |
| Testing         | pytest              |

## Project Structure

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
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Configuration

Configuration is stored in `.env`.

Example:

```env
OPENAI_API_KEY=your_api_key_here

OPENAI_MODEL=gpt-4o-mini
CODE_WORK_DIR=working

CODE_PREVIEW_MAX_LINES=50
CODE_PREVIEW_HEAD_LINES=25
CODE_PREVIEW_TAIL_LINES=25

MAX_FAILED_EXECUTIONS=3
MAX_TURNS=12
```

## Installation

Create a virtual environment and install the required dependencies.

```bash
python -m venv .venv
```

Activate the environment on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

## Running

Start docker desktop application and run this command:

```bash
python app/main.py
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

## Testing

Run the test suite with:

```powershell
python -m pytest
```

The tests cover the custom execution-failure termination logic.

## Key Agentic AI Concepts

* Multi-agent workflows
* Human-in-the-loop AI
* Tool calling
* Docker sandboxing
* Execution validation
* Automatic correction
* Feedback-driven refinement
* Retry strategies
* Termination conditions
* Separation of concerns
  
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

## License

This project is licensed under the MIT License.
