import unittest

from types import SimpleNamespace
from autogen_agentchat.messages import StopMessage, TextMessage
from app.termination_conditions import (
    ExecutorStatus,
    is_executor_result_rejected,
    is_executor_result_successful,
    MaxExecutionFailuresTermination
)


def executor_message(status: ExecutorStatus):
    """Create a lightweight executor message for unit tests."""
    content_by_status = {
        ExecutorStatus.SUCCESS: "Execution completed successfully.",
        ExecutorStatus.FAILURE: "POSIX exit code: 1. NameError",
        ExecutorStatus.REJECTED: "Code execution was not approved.",
        ExecutorStatus.DEPENDENCY_ERROR: (
            "POSIX exit code: 1. "
            "ModuleNotFoundError: No module named 'pygame'"
        ),
    }
    return SimpleNamespace(
        source="executor",
        content=content_by_status[status],
    )


class TestMaxExecutionFailuresTermination(
    unittest.IsolatedAsyncioTestCase
):
    async def test_stops_after_three_unique_failures(self):
        condition = MaxExecutionFailuresTermination(
            max_failed_executions=3
        )

        # First execution failure
        error_1 = TextMessage(
            source="executor",
            content="POSIX exit code: 1",
        )

        result = await condition([error_1])

        self.assertIsNone(result)
        self.assertEqual(condition.failed_execution_count, 1)

        # Second execution failure
        error_2 = TextMessage(
            source="executor",
            content="POSIX exit code: 1",
        )

        result = await condition([error_2])

        self.assertIsNone(result)
        self.assertEqual(condition.failed_execution_count, 2)

        # Third execution failure should terminate
        error_3 = TextMessage(
            source="executor",
            content="POSIX exit code: 1",
        )

        result = await condition([error_3])

        self.assertIsInstance(result, StopMessage)
        self.assertEqual(condition.failed_execution_count, 3)
        self.assertTrue(condition.terminated)

    async def test_non_executor_message_is_ignored(self):
        condition = MaxExecutionFailuresTermination(
            max_failed_executions=3
        )

        message = TextMessage(
            source="assistant",
            content="POSIX exit code: 1",
        )

        result = await condition([message])

        self.assertIsNone(result)
        self.assertEqual(condition.failed_execution_count, 0)

    async def test_dependency_error_does_not_increment_failure_count(self):
        condition = MaxExecutionFailuresTermination(
            max_failed_executions=3
        )

        result = await condition([executor_message(
            ExecutorStatus.DEPENDENCY_ERROR
        )])

        self.assertIsNone(result)
        self.assertEqual(condition.failed_execution_count, 0)
        self.assertFalse(condition.terminated)

    async def test_success_does_not_increment_failure_count(self):
        condition = MaxExecutionFailuresTermination(
            max_failed_executions=3
        )

        await condition([executor_message(ExecutorStatus.FAILURE)])
        result = await condition([executor_message(ExecutorStatus.SUCCESS)])

        self.assertIsNone(result)
        self.assertEqual(condition.failed_execution_count, 1)
        self.assertFalse(condition.terminated)

    async def test_stops_at_failure_limit(self):
        condition = MaxExecutionFailuresTermination(
            max_failed_executions=3
        )

        for _ in range(2):
            result = await condition([
                executor_message(ExecutorStatus.FAILURE)
            ])
            self.assertIsNone(result)

        result = await condition([
            executor_message(ExecutorStatus.FAILURE)
        ])

        self.assertIsNotNone(result)
        self.assertIn("Maximum failed execution count reached", result.content)
        self.assertTrue(condition.terminated)
        self.assertEqual(condition.failed_execution_count, 3)

    async def test_reset_allows_new_execution_cycle(self):
        condition = MaxExecutionFailuresTermination(
            max_failed_executions=2
        )

        await condition([executor_message(ExecutorStatus.FAILURE)])
        await condition([executor_message(ExecutorStatus.FAILURE)])

        self.assertTrue(condition.terminated)

        await condition.reset()

        self.assertFalse(condition.terminated)
        self.assertEqual(condition.failed_execution_count, 0)

        result = await condition([
            executor_message(ExecutorStatus.FAILURE)
        ])

        self.assertIsNone(result)
        self.assertEqual(condition.failed_execution_count, 1)

    async def test_successful_result_predicate(self):
        self.assertTrue(is_executor_result_successful([
            executor_message(ExecutorStatus.SUCCESS)
        ]))

    async def test_rejected_result_predicate(self):
        self.assertTrue(is_executor_result_rejected([
            executor_message(ExecutorStatus.REJECTED)
        ]))


if __name__ == "__main__":
    unittest.main()
