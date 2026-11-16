class JarvisError(Exception):
    pass

class ConfigError(JarvisError):
    pass

class LLMError(JarvisError):
    pass

class ToolError(JarvisError):
    pass

class PermissionDenied(JarvisError):
    pass

class SessionNotFound(JarvisError):
    pass

class AgentError(JarvisError):
    pass

class MemoryError(JarvisError):
    pass

class AudioError(JarvisError):
    pass

class ProviderNotFound(LLMError):
    pass

class ToolExecutionError(ToolError):
    pass
