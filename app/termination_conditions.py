from typing import Sequence
from autogen_agentchat.base import (
    TerminationCondition, TerminatedException,
)
from autogen_agentchat.messages import (
    BaseAgentEvent, BaseChatMessage, StopMessage
)


def is_executor_result_successful(
    messages: Sequence[BaseAgentEvent | BaseChatMessage],
) -> bool:
    """Return True when the latest executor message indicates success."""
    if not messages:
        return False

    last_message = messages[-1]

    if getattr(last_message, "source", None) != "executor":
        return False

    content = getattr(last_message, "content", "")

    if not isinstance(content, str):
        return False

    return "exited with an error" not in content


class MaxExecutionFailuresTermination(TerminationCondition):
    """Stop the team after too many failed code executions."""

    def __init__(self, max_failed_executions: int = 3) -> None:
        if max_failed_executions < 1:
            raise ValueError("max_failed_executions must be >= 1")

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

        if getattr(last_message, "source", None) != "executor":
            return None

        content = getattr(last_message, "content", "")

        if not isinstance(content, str):
            return None

        if "exited with an error" not in content:
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
