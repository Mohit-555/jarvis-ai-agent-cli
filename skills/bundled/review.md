---
name: Review Code
description: Review code for quality, bugs, and improvements
when-to-use: When the user asks for a code review
allowed-tools: [read_file, grep, web_search]
arguments: path
argument-hint: File or directory to review
user-invocable: true
version: 1.0
---

Review the code thoroughly and provide feedback on:
1. **Correctness**: Are there any bugs or logic errors?
2. **Security**: Are there security vulnerabilities (injection, XSS, auth issues)?
3. **Performance**: Are there performance bottlenecks?
4. **Maintainability**: Is the code easy to understand and modify?
5. **Style**: Does it follow language conventions?
6. **Testing**: Are there adequate tests? What's missing?

Rate each category as: ✅ Good | ⚠️ Needs Improvement | ❌ Critical

Provide specific, actionable recommendations.
