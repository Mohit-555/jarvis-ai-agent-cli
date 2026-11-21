import unittest
from tools.code.executor import CodeExecutor
from tools.os.shell import ShellTool


class TestPythonDevelopmentCapabilities(unittest.TestCase):
    """
    Verification of Tasks 36–55: Python Programming & Development.
    """

    def setUp(self):
        self.code_exec = CodeExecutor()
        self.shell = ShellTool()

    def test_task_36_37_factorial_and_prime_execution(self):
        """Tasks 36 & 37: Program execution for factorial and prime number logic."""
        code_fact = """
def factorial(n):
    return 1 if n <= 1 else n * factorial(n - 1)
print(factorial(5))
"""
        res_fact = self.code_exec.run_python(code_fact)
        self.assertTrue(res_fact["success"])
        self.assertEqual(res_fact["stdout"].strip(), "120")

        code_prime = """
def is_prime(n):
    if n < 2: return False
    return all(n % i != 0 for i in range(2, int(n**0.5) + 1))
print([x for x in range(2, 20) if is_prime(x)])
"""
        res_prime = self.code_exec.run_python(code_prime)
        self.assertTrue(res_prime["success"])
        self.assertIn("2, 3, 5, 7, 11, 13, 17, 19", res_prime["stdout"])

    def test_task_39_40_49_traceback_and_debugging(self):
        """Tasks 39, 40, 49: Error detection and traceback extraction."""
        broken_code = """
def divide(a, b):
    return a / b
divide(10, 0)
"""
        res_err = self.code_exec.run_python(broken_code)
        self.assertFalse(res_err["success"])
        self.assertIn("ZeroDivisionError", res_err["stderr"])

    def test_task_47_check_installed_packages(self):
        """Task 47: Check installed Python packages."""
        res = self.shell.run("python3 -m pip list")
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("Package", res["stdout"])
        self.assertIn("Version", res["stdout"])


if __name__ == "__main__":
    unittest.main()
