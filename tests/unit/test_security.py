import unittest
import os
import shutil
from pathlib import Path
from api.auth import AuthManager
from tools.code.executor import CodeExecutor
from security.sandboxing import Sandbox

class TestSecurity(unittest.TestCase):
    def test_auth_manager_api_key(self):
        auth = AuthManager()
        # Test explicit key registration
        auth.add_api_key("test-secret-key", "test-label")
        self.assertTrue(auth.verify_api_key("test-secret-key"))
        self.assertFalse(auth.verify_api_key("invalid-key"))

    def test_jwt_secret_persistence(self):
        # Verify a jwt_secret is generated and stored securely
        from core.config import KEYS_DIR
        secret_file = KEYS_DIR / "jwt_secret"
        
        # Instantiate AuthManager
        auth = AuthManager()
        self.assertTrue(len(auth.secret_key) > 0)
        self.assertTrue(secret_file.exists())
        
        # Verify the file is chmod 600
        mode = os.stat(secret_file).st_mode
        self.assertEqual(mode & 0o777, 0o600)

    def test_sandbox_and_docker(self):
        sandbox = Sandbox()
        # Verify blocked keywords are checked
        self.assertFalse(sandbox.check_code("import os"))
        self.assertFalse(sandbox.check_code("popen("))
        
        # Verify standard code works
        self.assertTrue(sandbox.check_code("result = 1 + 1"))
        
        # Verify execution
        res = sandbox.run_sandboxed("result = 42")
        self.assertTrue(res["success"])
        self.assertEqual(res["output"].strip(), "42")

    def test_code_executor(self):
        executor = CodeExecutor()
        res = executor.run_python("print('hello sandbox')")
        self.assertTrue(res["success"])
        self.assertEqual(res["stdout"].strip(), "hello sandbox")

    def test_config_encryption(self):
        os.environ["JARVIS_ENCRYPTION_KEY"] = "my-secret-key-12345"
        from core.config import save_config, load_config, CONFIG_FILE
        backup = None
        if CONFIG_FILE.exists():
            backup = CONFIG_FILE.read_text()
            
        try:
            cfg = load_config()
            cfg["openai_api_key"] = "super-secret-openai-token"
            save_config(cfg)
            
            raw_text = CONFIG_FILE.read_text()
            self.assertNotIn("super-secret-openai-token", raw_text)
            self.assertIn("enc::", raw_text)
            
            loaded_cfg = load_config()
            self.assertEqual(loaded_cfg["openai_api_key"], "super-secret-openai-token")
            
            mode = os.stat(CONFIG_FILE).st_mode
            self.assertEqual(mode & 0o777, 0o600)
        finally:
            del os.environ["JARVIS_ENCRYPTION_KEY"]
            if backup:
                CONFIG_FILE.write_text(backup)

if __name__ == "__main__":
    unittest.main()
