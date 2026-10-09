import asyncio

from autogen_agentchat.agents import (
    ApprovalResponse,
    AssistantAgent,
    CodeExecutorAgent,
)
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import FunctionalTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_ext.models.openai import OpenAIChatCompletionClient

from config import (
    CODE_PREVIEW_HEAD_LINES,
    CODE_PREVIEW_MAX_LINES,
    CODE_PREVIEW_TAIL_LINES,
    CODE_WORK_DIR,
    MAX_FAILED_EXECUTIONS,
    MAX_TURNS,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from prompts import PYTHON_ASSISTANT_SYSTEM_MESSAGE
from termination_conditions import (
    ExecutorStatus,
    get_executor_status,
    is_executor_result_rejected,
    is_executor_result_successful,
    MaxExecutionFailuresTermination,
)


def print_code_preview(code: str) -> None:
    """
    Display generated code for human approval.

    Large code blocks are truncated for readability,
    while the complete code is still passed to the executor.
    """

    lines = code.splitlines()
    total_lines = len(lines)

    print("\n" + "=" * 60)
    print(" CODE EXECUTION APPROVAL")
    print("=" * 60)
    print("\nGenerated Python code:")
    print("-" * 60)

    if total_lines <= CODE_PREVIEW_MAX_LINES:
        print(code)
    else:
        for line in lines[:CODE_PREVIEW_HEAD_LINES]:
            print(line)

        hidden_lines = (
            total_lines
            - CODE_PREVIEW_HEAD_LINES
            - CODE_PREVIEW_TAIL_LINES
        )

        print(f"\n... [{hidden_lines} lines hidden] ...\n")

        for line in lines[-CODE_PREVIEW_TAIL_LINES:]:
            print(line)

    print("-" * 60)
    print(f"Total lines: {total_lines}")


def approval_func(request) -> ApprovalResponse:
    """
    Ask the human user for permission before executing code.
    """

    print_code_preview(request.code)

    print("Execute this code?")
    print()
    print("[y] Yes, execute")
    print("[n] No, reject")

    while True:
        choice = input("\nYour choice: ").strip().lower()

        if choice == "y":
            print("[APPROVED] Code execution authorized.")

            return ApprovalResponse(
                approved=True,
                reason="User approved the code execution.",
            )

        if choice == "n":
            print("[REJECTED] Code execution denied.")

            return ApprovalResponse(
                approved=False,
                reason="User rejected the code execution.",
            )

        print("Please enter 'y' or 'n'.")


async def main() -> None:

    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is not configured."
        )

    model_client = OpenAIChatCompletionClient(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
    )

    assistant = AssistantAgent(
        name="assistant",
        model_client=model_client,
        system_message=PYTHON_ASSISTANT_SYSTEM_MESSAGE,
    )

    # Code execution is isolated inside a Docker container.
    code_executor = DockerCommandLineCodeExecutor(
        work_dir=CODE_WORK_DIR,
    )

    # The executor is intentionally used without a model client.
    # Code generation and correction are handled by AssistantAgent.
    executor = CodeExecutorAgent(
        name="executor",
        code_executor=code_executor,
        approval_func=approval_func,
    )

    # Stop when execution succeeds or the maximum number
    # of failed executions is reached.
    successful_execution = FunctionalTermination(
        is_executor_result_successful
    )

    rejection_termination = FunctionalTermination(
        is_executor_result_rejected
    )

    max_failures_termination = MaxExecutionFailuresTermination(
        max_failed_executions=MAX_FAILED_EXECUTIONS
    )

    termination = (
        successful_execution
        | rejection_termination
        | max_failures_termination
    )

    team = RoundRobinGroupChat(
        [assistant, executor],
        termination_condition=termination,
        max_turns=MAX_TURNS,
    )

    print("\n" + "=" * 60)
    print("              AI PYTHON CODE BUILDER")
    print("=" * 60)

    print("\nWhat Python program would you like to build?")

    user_request = input("> ").strip()

    if not user_request:
        print("\nNo request provided.")
        return

    # Start the Docker executor before running the team.
    await code_executor.start()

    try:
        # Stream agent messages so the CLI can display
        # code generation, approval, execution, and retry steps.
        stream = team.run_stream(task=user_request)

        # stream variables
        executor_status = None
        assistant_code_attempt = 0

        async for message in stream:

            if isinstance(message, TaskResult):
                if message.stop_reason:
                    print()
                    print("=" * 60)
                    print("                    TERMINATION")
                    print("=" * 60)
                    print()

                    if executor_status == ExecutorStatus.SUCCESS:
                        print("Code execution completed successfully.")

                    elif executor_status == ExecutorStatus.REJECTED:
                        print("Code execution was rejected by the user.")

                    else:
                        print(message.stop_reason)

                    print()

                continue

            source = getattr(message, "source", None)
            content = getattr(message, "content", None)

            if source == "user":
                continue

            elif source == "assistant":
                print("\nASSISTANT")
                print("-" * 60)

                if isinstance(content, str):
                    if "```python" in content:
                        assistant_code_attempt += 1

                        if assistant_code_attempt == 1:
                            print(
                                "Initial Python code is ready "
                                "for review."
                            )
                        else:
                            retry_number = (
                                assistant_code_attempt - 1
                            )

                            print(
                                f"Retry #{retry_number}: "
                                "Corrected Python code is ready "
                                "for review."
                            )
                    else:
                        print(content)

            elif source == "executor":
                if not isinstance(content, str):
                    continue

                print("\nEXECUTOR")
                print("-" * 60)

                executor_status = get_executor_status(message)
                if executor_status == ExecutorStatus.FAILURE:
                    failure_count = (
                        max_failures_termination
                        .failed_execution_count
                        + 1
                    )

                    print(
                        f"Execution failed "
                        f"({failure_count}/{MAX_FAILED_EXECUTIONS})"
                    )

                print(content)

    finally:
        await code_executor.stop()
        await model_client.close()


if __name__ == "__main__":
    asyncio.run(main())
