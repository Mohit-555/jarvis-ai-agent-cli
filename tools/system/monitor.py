import psutil


class SystemMonitor:
    def cpu(self):
        return {
            "percent": psutil.cpu_percent(interval=0.5),
            "count": psutil.cpu_count(),
            "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
        }

    def memory(self):
        return psutil.virtual_memory()._asdict()

    def disk(self):
        return psutil.disk_usage("/")._asdict()

    def network(self):
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
