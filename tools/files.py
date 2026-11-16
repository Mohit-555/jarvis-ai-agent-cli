from tools.os.file_manager import FileManagerTool
from tools.code.executor import CodeExecutor


class FileTool:
    def __init__(self, workspace=None):
        self.fm = FileManagerTool(workspace)
        self.ce = CodeExecutor()

    def read_file(self, path):
        return self.fm.read(path)

    def write_file(self, path, content):
        return self.fm.write(path, content)

    def list_dir(self, path="."):
        return self.fm.list(path)

    def search_files(self, pattern, path="."):
        return self.fm.search(pattern, path)

    def run_python(self, code):
        return self.ce.run_python(code)
