import unittest
from autogen_agentchat.messages import StopMessage, TextMessage
from app.termination_conditions import (MaxExecutionFailuresTermination)


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
            content="The script ran, then exited with an error",
        )

        result = await condition([error_1])

        self.assertIsNone(result)
        self.assertEqual(condition.failed_execution_count, 1)

        # Second execution failure
        error_2 = TextMessage(
            source="executor",
            content="The script ran, then exited with an error",
        )

        result = await condition([error_2])

        self.assertIsNone(result)
        self.assertEqual(condition.failed_execution_count, 2)

        # Third execution failure should terminate
        error_3 = TextMessage(
            source="executor",
            content="The script ran, then exited with an error",
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
            content="The script ran, then exited with an error",
        )

        result = await condition([message])

        self.assertIsNone(result)
        self.assertEqual(condition.failed_execution_count, 0)

    async def test_reset_clears_failure_count(self):
        condition = MaxExecutionFailuresTermination(
            max_failed_executions=3
        )

        error = TextMessage(
            source="executor",
            content="The script ran, then exited with an error",
        )

        await condition([error])
        await condition.reset()

        self.assertEqual(condition.failed_execution_count, 0)
        self.assertFalse(condition.terminated)


if __name__ == "__main__":
    unittest.main()
