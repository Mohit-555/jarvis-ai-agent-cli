import logging
import time
from collections import defaultdict

logger = logging.getLogger('jarvis.observability.metrics')

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False


class MetricsCollector:
    def __init__(self):
        self._counters: dict[str, dict] = defaultdict(lambda: defaultdict(int))
        self._histograms: dict[str, list] = defaultdict(list)
        self._gauges: dict[str, float] = {}
        self._prometheus_metrics: dict[str, object] = {}

    def increment(self, counter: str, labels: dict = None, value: int = 1):
        labels = labels or {}
        label_key = tuple(sorted(labels.items()))
        self._counters[counter][label_key] += value
        if HAS_PROMETHEUS:
            prom_key = (counter, str(labels))
            if prom_key not in self._prometheus_metrics:
                label_names = list(labels.keys())
                self._prometheus_metrics[prom_key] = Counter(
                    counter.replace(" ", "_").replace(".", "_"),
                    counter,
                    label_names,
                )
            self._prometheus_metrics[prom_key].labels(**labels).inc(value)

    def observe(self, histogram: str, value: float, labels: dict = None):
        labels = labels or {}
        label_key = tuple(sorted(labels.items()))
        self._histograms[histogram].append((value, time.time(), label_key))
        if HAS_PROMETHEUS:
            prom_key = (histogram, str(labels))
            if prom_key not in self._prometheus_metrics:
                label_names = list(labels.keys())
                self._prometheus_metrics[prom_key] = Histogram(
                    histogram.replace(" ", "_").replace(".", "_"),
                    histogram,
                    label_names,
                )
            self._prometheus_metrics[prom_key].labels(**labels).observe(value)

    def gauge(self, name: str, value: float, labels: dict = None):
        key = (name, str(labels or {}))
        self._gauges[key] = value
        if HAS_PROMETHEUS:
            if key not in self._prometheus_metrics:
                label_names = list((labels or {}).keys())
                self._prometheus_metrics[key] = Gauge(
                    name.replace(" ", "_").replace(".", "_"),
                    name,
                    label_names,
                )
            prom_labels = (labels or {})
            self._prometheus_metrics[key].labels(**prom_labels).set(value)

    def get_counter(self, name: str) -> int:
        return sum(self._counters[name].values())

    def get_histogram_stats(self, name: str) -> dict:
        values = [v[0] for v in self._histograms[name]]
        if not values:
            return {"count": 0, "mean": 0, "min": 0, "max": 0}
        return {
            "count": len(values),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    def get_gauge(self, name: str) -> float:
        matching = [v for k, v in self._gauges.items() if k[0] == name]
        return matching[-1] if matching else 0.0

    def get_all_metrics(self) -> dict:
        return {
            "counters": {k: dict(v) for k, v in self._counters.items()},
            "histograms": {k: self.get_histogram_stats(k) for k in self._histograms},
            "gauges": {k[0]: v for k, v in self._gauges.items()},
        }

    def generate_prometheus(self) -> bytes:
        if HAS_PROMETHEUS:
            return generate_latest(REGISTRY)
        return b""


metrics = MetricsCollector()
