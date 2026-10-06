import asyncio

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
    is_executor_error, is_executor_result_successful,
    MaxExecutionFailuresTermination
)

from autogen_agentchat.agents import (
    ApprovalResponse,
    AssistantAgent, CodeExecutorAgent
)
from autogen_agentchat.base import TaskResult
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import FunctionalTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor


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

        print(
            f"\n... [{hidden_lines} lines hidden] ...\n"
        )

        for line in lines[-CODE_PREVIEW_TAIL_LINES:]:
            print(line)

    print("-" * 60)
    print(f"Total lines: {total_lines}")


def approval_func(request):
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


async def main():

    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is not configured."
        )

    model_client = OpenAIChatCompletionClient(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
        )

    # Agent that uses the LLM
    assistant = AssistantAgent(
            name="assistant",
            model_client=model_client,
            system_message=PYTHON_ASSISTANT_SYSTEM_MESSAGE
        )

    # Agent that represents the user
    # user_proxy = UserProxyAgent(
    #    name="user_proxy",
    #    input_func=input,
    # )

    # Code executor
    code_executor = DockerCommandLineCodeExecutor(
        work_dir=CODE_WORK_DIR
    )

    # Docker container'ı başlat
    await code_executor.start()

    # Agent responsible for executing Python code
    executor = CodeExecutorAgent(
        name="executor",
        code_executor=code_executor,
        approval_func=approval_func,
    )

    successful_execution = FunctionalTermination(
        is_executor_result_successful
    )
    max_failures_termination = MaxExecutionFailuresTermination(
        max_failed_executions=MAX_FAILED_EXECUTIONS
    )
    termination = (
        successful_execution | max_failures_termination
    )

    # Orchestrate the conversation
    team = RoundRobinGroupChat(
        [assistant, executor],
        termination_condition=termination,
        max_turns=MAX_TURNS
    )

    try:
        print()
        print("=" * 60)
        print("              AI PYTHON CODE BUILDER")
        print("=" * 60)

        user_request = input(
            "\nWhat Python program would you like to build?\n> "
        )

        # Run the conversation and stream the messages
        stream = team.run_stream(task=user_request)

        first_assistant_message = True

        async for message in stream:

            if isinstance(message, TaskResult):
                if message.stop_reason:
                    print()
                    print("=" * 60)
                    print("                    TERMINATION")
                    print("=" * 60)
                    print()
                    print(message.stop_reason)
                    print()
                continue

            # Ignore user message.
            if message.source == "user":
                continue

            # Assistant message
            if message.source == "assistant":

                if first_assistant_message:
                    print()
                    print("ASSISTANT")
                    print("-" * 60)
                    print("Generated Python code is ready for review.")
                    first_assistant_message = False
                else:
                    print()
                    print("ASSISTANT")
                    print("-" * 60)
                    print(
                        "Generated corrected Python code is ready "
                        "for review."
                    )

                continue

            # Executor message
            if message.source == "executor":
                print()
                print("EXECUTOR")
                print("-" * 60)
                print(message.content)

                # Execution failure logging
                if (
                    isinstance(message.content, str)
                    and "exited with an error" in message.content
                ):
                    failure_count = (
                        max_failures_termination.failed_execution_count + 1
                    )

                    print()
                    print("-" * 60)
                    print(
                        f"EXECUTION FAILURE: "
                        f"{failure_count}/"
                        f"{max_failures_termination.max_failed_executions}"
                    )
                    print("-" * 60)

    finally:
        await code_executor.stop()
        await model_client.close()

if __name__ == "__main__":
    asyncio.run(main())
