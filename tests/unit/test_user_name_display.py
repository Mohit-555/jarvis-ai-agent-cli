import unittest
from cli import _user_line
from jarvis_input import _prompt_str

class TestUserNameDisplay(unittest.TestCase):
    def test_user_line_with_first_name(self):
        line = _user_line("Hello world", user_name="Mohit Patel")
        plain = line.plain
        self.assertTrue(plain.startswith("Mohit › Hello world"))

    def test_user_line_fallback_to_you(self):
        line = _user_line("Test message", user_name="")
        plain = line.plain
        self.assertTrue(plain.startswith("YOU › Test message") or plain.startswith("Mohit › Test message"))

    def test_prompt_str_with_first_name(self):
        ptk_prompt = _prompt_str("Mohit Patel")
        # Extract text from FormattedText
        text_content = "".join(part[1] for part in ptk_prompt)
        self.assertEqual(text_content, "Mohit ›  ")

    def test_prompt_str_fallback(self):
        ptk_prompt = _prompt_str("")
        text_content = "".join(part[1] for part in ptk_prompt)
        self.assertEqual(text_content, "YOU ›  ")

if __name__ == "__main__":
    unittest.main()
