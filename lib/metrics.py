class MetricsCollector:
    """
    A simple metrics collector.
    This is a placeholder for a real metrics collection system.
    It currently just prints metrics to the console.
    """

    def increment(self, name: str, value: int = 1):
        """
        Increments a counter.
        """
        print(f"METRIC: {name} | COUNT | {value}")

    def gauge(self, name: str, value: float):
        """
        Sets a gauge to a specific value.
        """
        print(f"METRIC: {name} | GAUGE | {value}")


# A global instance of the metrics collector
metrics = MetricsCollector()
