import os
import asyncio

from dotenv import load_dotenv
from app.termination_conditions import (
    is_executor_result_successful, MaxExecutionFailuresTermination,
)
from autogen_agentchat.agents import (
    ApprovalRequest,
    ApprovalResponse,
    AssistantAgent,
    # UserProxyAgent,
    CodeExecutorAgent,
)
from autogen_agentchat.ui import Console
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import FunctionalTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor


load_dotenv()


def approval_func(request: ApprovalRequest) -> ApprovalResponse:
    print("\n" + "=" * 60)
    print("CODE EXECUTION APPROVAL")
    print("=" * 60)

    print(request.code)

    answer = input("\nExecute this code? (y/n): ").strip().lower()

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
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY"),
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
        work_dir="working"
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
        max_failed_executions=3
    )
    termination = (
        successful_execution | max_failures_termination 
    )

    # Orchestrate the conversation
    team = RoundRobinGroupChat(
        [assistant, executor],
        termination_condition=termination,
        max_turns=12,
    )

    try:
        user_request = input(
            "\nWhat Python program would you like to build?\n> "
        )
        # Run the conversation and stream the messages
        await Console(
            team.run_stream(
                task=user_request,
            )
        )
    finally:
        await code_executor.stop()
        await model_client.close()

if __name__ == "__main__":
    asyncio.run(main())
