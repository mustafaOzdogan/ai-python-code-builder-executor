from typing import Sequence
from autogen_agentchat.base import (
    TerminationCondition, TerminatedException,
)
from autogen_agentchat.messages import (
    BaseChatMessage, StopMessage, BaseAgentEvent
)


def is_executor_error(
    message: BaseAgentEvent | BaseChatMessage
) -> bool:
    """ Determine whether the executor message represents
    a failed code execution

    In AutoGen 0.7.5, when CodeExecutorAgent is used
    without a model_client, the execution result is
    exposed as a TextMessage.

    Therefore, for this PoC, we detect execution failure
    from the executor's output message.
    """

    if getattr(message, "source", None) != "executor":
        return False

    content = getattr(message, "content", "")

    if not isinstance(content, str):
        return False

    return "POSIX exit code:" in content


def is_executor_result_successful(
    messages: Sequence[BaseAgentEvent | BaseChatMessage]
) -> bool:
    """
    Return True when the latest executor result
    represents a successful execution.
    """

    if not messages:
        return False

    last_message = messages[-1]

    if getattr(last_message, "source", None) != "executor":
        return False

    return not is_executor_error(last_message)


class MaxExecutionFailuresTermination(TerminationCondition):
    """
    Stop the team after too many failed code executions.
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

        last_message = messages[-1]

        if not is_executor_error(last_message):
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
