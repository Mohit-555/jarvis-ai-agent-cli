---
name: Generate Tests
description: Generate unit tests for code
when-to-use: When the user asks to write tests for code
allowed-tools: [read_file, write_file, shell_exec, run_python]
arguments: target
argument-hint: File to generate tests for
user-invocable: true
version: 1.0
---

Generate comprehensive unit tests for the given code:
1. Read the source file thoroughly
2. Identify all public functions, classes, and methods
3. Write tests covering:
   - Normal cases (expected inputs)
   - Edge cases (empty, boundary values)
   - Error cases (invalid inputs, exceptions)
4. Use the appropriate testing framework (pytest for Python, jest for JS, etc.)
5. Mock external dependencies
6. Write the tests to an appropriate test file
7. Run the tests to verify they pass
