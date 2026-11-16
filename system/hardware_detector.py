import os
import sys
import platform
import subprocess
import shutil
import ctypes

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

HAS_CUDA = False
HAS_ROCM = False
HAS_MPS = False

try:
    import torch
    HAS_CUDA = torch.cuda.is_available()
    HAS_MPS = torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False
except ImportError:
    pass

try:
    result = subprocess.run(['rocm-smi'], capture_output=True, text=True, timeout=5)
    HAS_ROCM = result.returncode == 0
except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
    pass


def get_ram_gb():
    if HAS_PSUTIL:
        total = psutil.virtual_memory().total
        return round(total / (1024 ** 3), 1)
    try:
        if sys.platform == 'linux':
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        kb = int(line.split()[1])
                        return round(kb / (1024 ** 2), 1)
    except Exception:
        pass
    return 0


def get_ram_available_gb():
    if HAS_PSUTIL:
        avail = psutil.virtual_memory().available
        return round(avail / (1024 ** 3), 1)
    try:
        if sys.platform == 'linux':
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemAvailable:'):
                        kb = int(line.split()[1])
                        return round(kb / (1024 ** 2), 1)
    except Exception:
        pass
    return 0


def get_cpu_cores():
    if HAS_PSUTIL:
        return psutil.cpu_count(logical=True)
    try:
        if sys.platform == 'linux':
            return len(os.sched_getaffinity(0))
    except AttributeError:
        pass
    return os.cpu_count() or 1


def get_gpu_info():
    gpu_info = {
        'available': False,
        'type': 'none',
        'name': None,
        'vram_gb': 0,
        'cuda': HAS_CUDA,
        'rocm': HAS_ROCM,
        'mps': HAS_MPS,
    }

    if HAS_CUDA:
        import torch
        gpu_info['available'] = True
        gpu_info['type'] = 'nvidia'
        gpu_info['name'] = torch.cuda.get_device_name(0)
        try:
            gpu_info['vram_gb'] = round(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 1)
        except Exception:
            gpu_info['vram_gb'] = 0
        return gpu_info

    if HAS_ROCM:
        gpu_info['available'] = True
        gpu_info['type'] = 'amd'
        try:
            result = subprocess.run(
                ['rocm-smi', '--showproductname'],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'Name' in line or 'Product' in line:
                    gpu_info['name'] = line.split(':')[-1].strip()
                    break
        except Exception:
            gpu_info['name'] = 'AMD GPU'
        return gpu_info

    if HAS_MPS:
        gpu_info['available'] = True
        gpu_info['type'] = 'apple'
        gpu_info['name'] = 'Apple Silicon (MPS)'
        return gpu_info

    try:
        if sys.platform == 'linux':
            result = subprocess.run(
                ['lspci'],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'VGA' in line or '3D' in line or 'Display' in line:
                    gpu_info['name'] = line.split(':')[-1].strip()
                    if 'NVIDIA' in line or 'nvidia' in line:
                        gpu_info['type'] = 'nvidia'
                    elif 'AMD' in line or 'Advanced Micro Devices' in line:
                        gpu_info['type'] = 'amd'
                    elif 'Intel' in line:
                        gpu_info['type'] = 'intel'
                    gpu_info['available'] = True
                    break
    except Exception:
        pass

    return gpu_info


def get_disk_gb(path='/'):
    if HAS_PSUTIL:
        usage = psutil.disk_usage(path)
        return {
            'total_gb': round(usage.total / (1024 ** 3), 1),
            'free_gb': round(usage.free / (1024 ** 3), 1),
        }
    try:
        if sys.platform == 'linux':
            stat = os.statvfs(path)
            total = stat.f_frsize * stat.f_blocks
            free = stat.f_frsize * stat.f_bfree
            return {
                'total_gb': round(total / (1024 ** 3), 1),
                'free_gb': round(free / (1024 ** 3), 1),
            }
    except Exception:
        pass
    return {'total_gb': 0, 'free_gb': 0}


def get_platform_info():
    return {
        'system': platform.system(),
        'release': platform.release(),
        'machine': platform.machine(),
        'processor': platform.processor() or platform.machine(),
        'python': sys.version.split()[0],
    }


def get_audio_devices():
    devices = {'input': False, 'output': False, 'input_devices': [], 'output_devices': []}
    try:
        import sounddevice as sd
        devs = sd.query_devices()
        for i, dev in enumerate(devs):
            if dev['max_input_channels'] > 0:
                devices['input'] = True
                devices['input_devices'].append(dev['name'])
            if dev['max_output_channels'] > 0:
                devices['output'] = True
                devices['output_devices'].append(dev['name'])
    except Exception:
        pass
    if sys.platform == 'linux':
        for path in ['/proc/asound/cards', '/dev/snd']:
            if os.path.exists(path):
                devices['input'] = True
                break
    return devices


def check_ollama():
    try:
        result = subprocess.run(
            ['ollama', 'list'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            models = []
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip():
                    models.append(line.split()[0])
            return {'installed': True, 'models': models}
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return {'installed': False, 'models': []}


def check_docker():
    try:
        result = subprocess.run(
            ['docker', 'info', '--format', '{{.ServerVersion}}'],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


def detect_all():
    ram = get_ram_gb()
    ram_avail = get_ram_available_gb()
    cpu = get_cpu_cores()
    gpu = get_gpu_info()
    disk = get_disk_gb()
    plat = get_platform_info()
    audio = get_audio_devices()
    ollama = check_ollama()

    ram_tier = 'low' if ram < 8 else 'medium' if ram < 16 else 'high' if ram < 32 else 'ultra'
    gpu_tier = 'none' if not gpu['available'] else 'low' if gpu.get('vram_gb', 0) < 6 else 'medium' if gpu.get('vram_gb', 0) < 12 else 'high'

    return {
        'ram': {
            'total_gb': ram,
            'available_gb': ram_avail,
            'tier': ram_tier,
        },
        'cpu': {
            'cores': cpu,
        },
        'gpu': gpu,
        'disk': disk,
        'platform': plat,
        'audio': audio,
        'ollama': ollama,
        'docker': check_docker(),
        'tiers': {
            'ram': ram_tier,
            'gpu': gpu_tier,
        },
        'summary': {
            'ram_label': f'{ram}GB' if ram else 'Unknown',
            'gpu_label': gpu['name'] or 'None',
            'cpu_label': f'{cpu} cores',
        },
    }
