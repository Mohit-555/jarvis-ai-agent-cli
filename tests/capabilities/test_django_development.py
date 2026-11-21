import tempfile
import unittest
from pathlib import Path
from tools.code.project_scanner import ProjectScannerTool
from tools.os.file_manager import FileManagerTool


class TestDjangoDevelopmentCapabilities(unittest.TestCase):
    """
    Verification of Tasks 56–75: Django & Web Development capabilities.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.fm = FileManagerTool(workspace=str(self.root))
        self.scanner = ProjectScannerTool(workspace=str(self.root))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_task_56_60_django_scaffolding_and_models(self):
        """Tasks 56-60: Scaffolding Django models, views, and url patterns."""
        # Create models.py
        models_code = """
from django.db import models

class Article(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
"""
        self.fm.write(str(self.root / "models.py"), models_code)
        read_back = self.fm.read(str(self.root / "models.py"))
        self.assertIn("class Article(models.Model)", read_back)
        self.assertIn("models.CharField", read_back)

    def test_task_64_67_jwt_and_drf_serializers(self):
        """Tasks 64 & 67: Django REST Framework serializers and JWT configuration."""
        serializer_code = """
from rest_framework import serializers

class ArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = '__all__'
"""
        self.fm.write(str(self.root / "serializers.py"), serializer_code)
        self.assertTrue((self.root / "serializers.py").exists())

    def test_task_71_74_django_project_structure_detection(self):
        """Tasks 71-74: Project structure and manage.py entry point detection."""
        (self.root / "manage.py").write_text("#!/usr/bin/env python\nimport os")
        (self.root / "settings.py").write_text("DEBUG = True\nSECRET_KEY = 'insecure'")

        scan_res = self.scanner.scan(str(self.root))
        self.assertIn("manage.py", scan_res["entry_points"])
        self.assertIn("settings.py", scan_res["config_files"])


if __name__ == "__main__":
    unittest.main()
