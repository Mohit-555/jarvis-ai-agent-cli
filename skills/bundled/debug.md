---
name: Debug
description: Debug code issues and find bugs
when-to-use: When the user encounters an error or unexpected behavior
allowed-tools: [read_file, shell_exec, run_python, grep, web_search]
arguments: issue
argument-hint: Error message or description of the bug
user-invocable: true
version: 1.0
---

Follow this debugging process:
1. Understand the error or unexpected behavior
2. Examine relevant code files and logs
3. Formulate hypotheses about root cause
4. Test each hypothesis (run tests, add logging, isolate variables)
5. Identify the root cause
6. Propose a fix with explanation
7. Verify the fix works

Be systematic. Look for common issues: type mismatches, null references, race conditions, incorrect imports, off-by-one errors.
