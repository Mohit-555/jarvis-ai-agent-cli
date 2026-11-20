try:
    import psutil
except ImportError:
    psutil = None


class SystemMonitor:
    def cpu(self):
        if not psutil:
            return {"percent": 0.0, "count": 1, "freq": {}}
        return {
            "percent": psutil.cpu_percent(interval=0.5),
            "count": psutil.cpu_count(),
            "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
        }

    def memory(self):
        if not psutil:
            return {"total": 0, "available": 0, "percent": 0}
        return psutil.virtual_memory()._asdict()

    def disk(self):
        if not psutil:
            return {"total": 0, "used": 0, "free": 0, "percent": 0}
        return psutil.disk_usage("/")._asdict()

    def network(self):
        if not psutil:
            return {}
        return psutil.net_io_counters()._asdict()

    def gpu(self):
        return {"available": False, "message": "No GPU detected (CPU-only system)"}

    def all_stats(self):
        return {
            "cpu": self.cpu(),
            "memory": self.memory(),
            "disk": self.disk(),
            "network": self.network(),
            "gpu": self.gpu(),
        }
