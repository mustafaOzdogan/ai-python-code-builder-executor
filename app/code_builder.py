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
from termination_conditions import (
    is_executor_result_successful,
    MaxExecutionFailuresTermination
)
from autogen_agentchat.agents import (
    ApprovalRequest, ApprovalResponse,
    AssistantAgent, CodeExecutorAgent
)
from autogen_agentchat.messages import StopMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import FunctionalTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor


def approval_func(request: ApprovalRequest) -> ApprovalResponse:
    print()
    print("=" * 60)
    print("                 CODE EXECUTION APPROVAL")
    print("=" * 60)
    print()
    print("The following code is ready for execution:")
    print()
    print("-" * 60)
    print(request.code)
    print("-" * 60)
    print()
    print("Execute this code?")
    print()
    print("[y] Yes, execute")
    print("[n] No, reject")
    print()

    answer = input("Your choice: ").strip().lower()

    if answer == "y":
        return ApprovalResponse(
            approved=True,
            reason="User approved the code execution.",
        )

    return ApprovalResponse(
        approved=False,
        reason="User rejected the code execution.",
    )


async def main():
    # OpenAI model client
    model_client = OpenAIChatCompletionClient(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
        )

    # Agent that uses the LLM
    assistant = AssistantAgent(
            name="assistant",
            model_client=model_client,
            system_message=(
                "You are a Python coding assistant. "
                "Your job is to build and execute Python programs "
                "based on the user's request. "

                "When the user provides a request, generate executable "
                "Python code inside a ```python code block. "

                "When the executor reports an execution error, "
                "analyze the error, fix the Python code, and provide "
                "the corrected code inside a ```python code block. "

                "Do not merely explain the error. "
                "Always provide corrected executable code when an "
                "execution error occurs. "

                "Do not claim that code was executed unless you "
                "receive the execution result from the executor."
            ),
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
                    print("Generated corrected Python code is ready for review.")

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
