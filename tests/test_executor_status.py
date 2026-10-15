
import unittest
from types import SimpleNamespace
from app.termination_conditions import ExecutorStatus, get_executor_status


class TestGetExecutorStatus(unittest.TestCase):

    def make_message(self, source="executor", content=""):
        return SimpleNamespace(source=source, content=content)

    def test_successful_execution(self):
        message = self.make_message(
            content="The factorial of 10 is: 3628800"
        )

        self.assertEqual(
            get_executor_status(message),
            ExecutorStatus.SUCCESS,
        )

    def test_runtime_error_is_failure(self):
        message = self.make_message(
            content=(
                "Command failed with exit code. "
                "POSIX exit code: 1. "
                "NameError: name 'result' is not defined"
            )
        )

        self.assertEqual(
            get_executor_status(message),
            ExecutorStatus.FAILURE,
        )

    def test_recursion_error_is_failure(self):
        message = self.make_message(
            content=(
                "POSIX exit code: 1. "
                "RecursionError: maximum recursion depth exceeded"
            )
        )

        self.assertEqual(
            get_executor_status(message),
            ExecutorStatus.FAILURE,
        )

    def test_missing_module_is_dependency_error(self):
        message = self.make_message(
            content=(
                "POSIX exit code: 1. "
                "ModuleNotFoundError: No module named 'pygame'"
            )
        )

        self.assertEqual(
            get_executor_status(message),
            ExecutorStatus.DEPENDENCY_ERROR,
        )

    def test_rejected_execution(self):
        message = self.make_message(
            content="Code execution was not approved."
        )

        self.assertEqual(
            get_executor_status(message),
            ExecutorStatus.REJECTED,
        )

    def test_non_executor_message_is_ignored(self):
        message = self.make_message(
            source="assistant",
            content="Here is the generated Python code."
        )

        self.assertIsNone(get_executor_status(message))

    def test_non_string_content_is_ignored(self):
        message = self.make_message(content={"output": "success"})

        self.assertIsNone(get_executor_status(message))


if __name__ == "__main__":
    unittest.main()
