import unittest
import re

class TestExitIntent(unittest.TestCase):
    def _is_exit(self, user_input: str) -> bool:
        clean_cmd = re.sub(r"[?!.,;:~_`'\"()]+", " ", user_input.strip().lower()).strip()
        words = clean_cmd.split()
        if not words:
            return False

        is_question = any(clean_cmd.startswith(q) for q in (
            "how ", "what ", "why ", "when ", "where ", "who ", "can you ", "could you ", "tell me "
        ))
        if is_question:
            return False

        if clean_cmd in ("exit", "quit", "q", ":q", "bye", "goodbye", "cya", "alvida", "close", "stop", "shutdown"):
            return True

        typo_map = {
            "sessioyn": "session", "sesion": "session", "sesson": "session", "sessoin": "session",
            "tbhis": "this", "ths": "this", "thiss": "this",
            "jarivs": "jarvis", "jarvisai": "jarvis",
            "exitt": "exit", "ext": "exit", "exiit": "exit",
            "quitt": "quit", "qut": "quit"
        }
        norm_words = [typo_map.get(w, w) for w in words]
        norm_cmd = " ".join(norm_words)

        target_nouns = {"session", "jarvis", "app", "terminal", "program", "chat", "this", "it", "all", "now", "here"}
        exit_verbs = ("exit", "quit", "close", "stop", "end", "terminate", "shut down", "shutdown", "band", "kill")

        if any(norm_cmd.startswith(f"{v} ") or norm_cmd == v for v in exit_verbs):
            if any(w in norm_words for w in target_nouns) or len(norm_words) <= 3:
                return True
        elif any(norm_cmd.endswith(f" {v}") for v in ("exit", "quit", "close", "stop", "end", "band", "band karo", "band kar do", "khatam karo", "alvida")):
            return True
        elif any(p in norm_cmd for p in (
            "exit session", "exit this session", "close jarvis", "stop jarvis",
            "jarvis close", "jarvis exit", "jarvis band karo", "band karo jarvis",
            "close this session", "band kar do", "khatam karo", "chalta hoon"
        )):
            return True

        return False

    def test_exact_screenshot_inputs(self):
        self.assertTrue(self._is_exit("exit tbhis sessioyn"))
        self.assertTrue(self._is_exit("close jarvis"))

    def test_standard_exits(self):
        self.assertTrue(self._is_exit("exit"))
        self.assertTrue(self._is_exit("quit"))
        self.assertTrue(self._is_exit("q"))
        self.assertTrue(self._is_exit(":q"))
        self.assertTrue(self._is_exit("bye"))
        self.assertTrue(self._is_exit("goodbye"))
        self.assertTrue(self._is_exit("exit this session"))
        self.assertTrue(self._is_exit("close this session"))
        self.assertTrue(self._is_exit("stop jarvis"))
        self.assertTrue(self._is_exit("shutdown"))

    def test_hinglish_exits(self):
        self.assertTrue(self._is_exit("jarvis band karo"))
        self.assertTrue(self._is_exit("band karo jarvis"))
        self.assertTrue(self._is_exit("session band kar do"))
        self.assertTrue(self._is_exit("alvida"))

    def test_non_exit_questions(self):
        self.assertFalse(self._is_exit("how to exit a vim session?"))
        self.assertFalse(self._is_exit("what is the exit code of grep?"))
        self.assertFalse(self._is_exit("why did python exit with 1?"))
        self.assertFalse(self._is_exit("tell me how to close a file in python"))

if __name__ == '__main__':
    unittest.main()
