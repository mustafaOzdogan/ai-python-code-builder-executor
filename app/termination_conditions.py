from enum import Enum
from collections.abc import Sequence

from autogen_agentchat.base import (
    TerminatedException,
    TerminationCondition,
)
from autogen_agentchat.messages import (
    BaseAgentEvent,
    BaseChatMessage,
    StopMessage
)


class ExecutorStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    REJECTED = "rejected"


def get_executor_status(
    message: BaseAgentEvent | BaseChatMessage,
) -> ExecutorStatus | None:
    """
    Determine the status of an executor message.

    In AutoGen 0.7.5, when CodeExecutorAgent is used
    without a model_client, the execution result is exposed
    as a TextMessage.
    """

    if getattr(message, "source", None) != "executor":
        return None

    content = getattr(message, "content", "")

    if not isinstance(content, str):
        return None

    if "Code execution was not approved." in content:
        return ExecutorStatus.REJECTED

    if "POSIX exit code:" in content:
        return ExecutorStatus.FAILURE

    return ExecutorStatus.SUCCESS


def is_executor_result_successful(
    messages: Sequence[BaseAgentEvent | BaseChatMessage],
) -> bool:
    """
    Return True when the latest executor result is successful.
    """

    if not messages:
        return False

    return (
        get_executor_status(messages[-1])
        == ExecutorStatus.SUCCESS
    )


def is_executor_result_rejected(
    messages: Sequence[BaseAgentEvent | BaseChatMessage],
) -> bool:
    """
    Return True when the latest executor result was rejected.
    """

    if not messages:
        return False

    return (
        get_executor_status(messages[-1])
        == ExecutorStatus.REJECTED
    )


class MaxExecutionFailuresTermination(TerminationCondition):
    """
    Stop the team after the maximum number of failed
    code executions is reached.
    """

    def __init__(self, max_failed_executions: int = 3) -> None:
        if max_failed_executions < 1:
            raise ValueError(
                "max_failed_executions must be >= 1"
            )

        self.max_failed_executions = max_failed_executions
        self.failed_execution_count = 0
        self._terminated = False

    @property
    def terminated(self) -> bool:
        return self._terminated

    async def __call__(
        self,
        messages: Sequence[BaseAgentEvent | BaseChatMessage],
    ) -> StopMessage | None:
        if self._terminated:
            raise TerminatedException(
                "Termination condition has already been reached"
            )

        if not messages:
            return None

        status = get_executor_status(messages[-1])

        if status != ExecutorStatus.FAILURE:
            return None

        self.failed_execution_count += 1

        if self.failed_execution_count >= self.max_failed_executions:
            self._terminated = True

            return StopMessage(
                content=(
                    "Maximum failed execution count reached: "
                    f"{self.max_failed_executions}."
                ),
                source="MaxExecutionFailuresTermination",
            )

        return None

    async def reset(self) -> None:
        self.failed_execution_count = 0
        self._terminated = False
