---
name: Refactor
description: Refactor and improve code quality
when-to-use: When the user asks to improve, clean up, or modernize code
allowed-tools: [read_file, write_file, shell_exec, run_python]
arguments: target
argument-hint: File or directory to refactor
user-invocable: true
version: 1.0
---

Improve the code following these principles:
1. Extract duplicate logic into shared functions
2. Improve naming for clarity
3. Reduce function complexity (break large functions apart)
4. Add proper error handling
5. Follow language idioms and conventions
6. Keep the public API stable unless asked otherwise
7. Preserve existing behavior - don't change functionality

After refactoring, explain what changed and why.
