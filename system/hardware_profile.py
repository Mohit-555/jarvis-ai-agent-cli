HARDWARE_PROFILES = {
    'minimal': {
        'label': 'Minimal (8GB RAM, no GPU)',
        'ram_min': 0,
        'ram_max': 8.5,
        'gpu_vram_min': 0,
        'gpu_vram_max': 0,
        'config': {
            'llm_provider': 'ollama',
            'ollama_model': 'phi:latest',
            'stt_model': 'tiny',
            'tts_engine': 'pyttsx3',
            'memory_backend': 'chroma',
            'enable_voice': False,
            'enable_vision': False,
            'enable_browser': False,
            'enable_code_exec': True,
            'enable_redis': False,
            'enable_postgres': False,
            'enable_web_search': True,
            'enable_system_control': True,
            'rag_chunk_size': 512,
            'max_concurrent_tools': 1,
            'agent_max_iterations': 5,
        },
    },
    'low': {
        'label': 'Low (8-16GB RAM, no GPU)',
        'ram_min': 8,
        'ram_max': 16,
        'gpu_vram_min': 0,
        'gpu_vram_max': 0,
        'config': {
            'llm_provider': 'ollama',
            'ollama_model': 'llama3.2:3b',
            'stt_model': 'tiny',
            'tts_engine': 'pyttsx3',
            'memory_backend': 'chroma',
            'enable_voice': True,
            'enable_vision': False,
            'enable_browser': True,
            'enable_code_exec': True,
            'enable_redis': False,
            'enable_postgres': False,
            'enable_web_search': True,
            'enable_system_control': True,
            'rag_chunk_size': 512,
            'max_concurrent_tools': 1,
            'agent_max_iterations': 8,
        },
    },
    'medium': {
        'label': 'Medium (16-32GB RAM, low-end GPU or none)',
        'ram_min': 16,
        'ram_max': 32,
        'gpu_vram_min': 0,
        'gpu_vram_max': 0,
        'config': {
            'llm_provider': 'ollama',
            'ollama_model': 'llama3.1:8b',
            'stt_model': 'base',
            'tts_engine': 'edge-tts',
            'memory_backend': 'chroma',
            'enable_voice': True,
            'enable_vision': True,
            'enable_browser': True,
            'enable_code_exec': True,
            'enable_redis': True,
            'enable_postgres': False,
            'enable_web_search': True,
            'enable_system_control': True,
            'rag_chunk_size': 1024,
            'max_concurrent_tools': 2,
            'agent_max_iterations': 10,
        },
    },
    'high': {
        'label': 'High (32GB+ RAM, 6GB+ GPU)',
        'ram_min': 32,
        'ram_max': float('inf'),
        'gpu_vram_min': 6,
        'gpu_vram_max': float('inf'),
        'config': {
            'llm_provider': 'ollama',
            'ollama_model': 'llama3.1:8b',
            'stt_model': 'base',
            'tts_engine': 'coqui',
            'memory_backend': 'chroma+pgvector',
            'enable_voice': True,
            'enable_vision': True,
            'enable_browser': True,
            'enable_code_exec': True,
            'enable_redis': True,
            'enable_postgres': True,
            'enable_web_search': True,
            'enable_system_control': True,
            'rag_chunk_size': 2048,
            'max_concurrent_tools': 3,
            'agent_max_iterations': 15,
        },
    },
    'ultra': {
        'label': 'Ultra (64GB+ RAM, 12GB+ GPU)',
        'ram_min': 64,
        'ram_max': float('inf'),
        'gpu_vram_min': 12,
        'gpu_vram_max': float('inf'),
        'config': {
            'llm_provider': 'ollama',
            'ollama_model': 'llama3.1:70b',
            'stt_model': 'large',
            'tts_engine': 'coqui',
            'memory_backend': 'chroma+pgvector+redis',
            'enable_voice': True,
            'enable_vision': True,
            'enable_browser': True,
            'enable_code_exec': True,
            'enable_redis': True,
            'enable_postgres': True,
            'enable_web_search': True,
            'enable_system_control': True,
            'rag_chunk_size': 2048,
            'max_concurrent_tools': 5,
            'agent_max_iterations': 20,
        },
    },
}

PROFILE_ORDER = ['minimal', 'low', 'medium', 'high', 'ultra']


def get_hardware_profile(hw):
    ram_gb = hw['ram']['total_gb']
    gpu_vram = hw['gpu'].get('vram_gb', 0)
    gpu_type = hw['gpu'].get('type', 'none')
    has_gpu = hw['gpu']['available']

    for pid in reversed(PROFILE_ORDER):
        p = HARDWARE_PROFILES[pid]
        ram_match = p['ram_min'] <= ram_gb < p['ram_max']
        if has_gpu:
            vram_match = p['gpu_vram_min'] <= gpu_vram < p['gpu_vram_max']
        else:
            vram_match = p['gpu_vram_min'] == 0 and p['gpu_vram_max'] == 0
        if ram_match and vram_match:
            return pid, p
    return 'minimal', HARDWARE_PROFILES['minimal']


def get_adaptive_config(hw):
    profile_id, profile = get_hardware_profile(hw)
    config = dict(profile['config'])

    if hw['gpu']['cuda']:
        config['device'] = 'cuda'
    elif hw['gpu']['mps']:
        config['device'] = 'mps'
    else:
        config['device'] = 'cpu'

    if not hw['audio']['input']:
        config['enable_voice'] = False

    if hw['ollama']['installed'] and hw['ollama']['models']:
        models = hw['ollama']['models']
        preferred = config.get('ollama_model', '').split(':')[0]
        matching = [m for m in models if m.startswith(preferred)]
        if not matching:
            matching = sorted(models, key=lambda x: len(x))
        if matching:
            config['ollama_model'] = matching[-1]

    return config, profile_id, profile
