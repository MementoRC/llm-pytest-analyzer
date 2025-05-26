#!/usr/bin/env python3
"""
Comprehensive memory monitoring for pytest-analyzer GUI to identify real memory issues.
"""

import gc
import logging
import resource
import threading
import time
from pathlib import Path

import psutil


class MemoryMonitor:
    """Detailed memory monitoring and reporting."""

    def __init__(self, interval=1.0):
        self.interval = interval
        self.running = False
        self.thread = None
        self.process = psutil.Process()
        self.peak_memory = 0
        self.measurements = []

        # Configure logging to file and console
        log_file = Path(__file__).parent / "memory_monitor.log"
        file_handler = logging.FileHandler(log_file, mode="w")
        console_handler = logging.StreamHandler()

        formatter = logging.Formatter("%(asctime)s - MEMORY - %(message)s")
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        self.logger = logging.getLogger("MemoryMonitor")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def get_memory_info(self):
        """Get comprehensive memory information."""
        # Process memory
        proc_memory = self.process.memory_info()
        proc_memory_percent = self.process.memory_percent()

        # System memory
        sys_memory = psutil.virtual_memory()
        swap_memory = psutil.swap_memory()

        # Python garbage collection
        gc_counts = gc.get_count()

        # Resource limits
        try:
            memory_limit = resource.getrlimit(resource.RLIMIT_AS)
        except OSError:
            memory_limit = (None, None)

        info = {
            "timestamp": time.time(),
            "process_rss_mb": proc_memory.rss / 1024 / 1024,
            "process_vms_mb": proc_memory.vms / 1024 / 1024,
            "process_percent": proc_memory_percent,
            "system_total_gb": sys_memory.total / 1024 / 1024 / 1024,
            "system_used_gb": sys_memory.used / 1024 / 1024 / 1024,
            "system_free_gb": sys_memory.free / 1024 / 1024 / 1024,
            "system_available_gb": sys_memory.available / 1024 / 1024 / 1024,
            "system_percent": sys_memory.percent,
            "swap_total_gb": swap_memory.total / 1024 / 1024 / 1024,
            "swap_used_gb": swap_memory.used / 1024 / 1024 / 1024,
            "swap_percent": swap_memory.percent,
            "gc_gen0": gc_counts[0],
            "gc_gen1": gc_counts[1],
            "gc_gen2": gc_counts[2],
            "memory_limit_mb": memory_limit[0] / 1024 / 1024 if memory_limit[0] else None,
        }

        # Track peak
        if info["process_rss_mb"] > self.peak_memory:
            self.peak_memory = info["process_rss_mb"]

        return info

    def log_memory_state(self, context=""):
        """Log current memory state with context."""
        info = self.get_memory_info()

        self.logger.info(f"=== MEMORY STATE {context} ===")
        self.logger.info(
            f"Process: RSS={info['process_rss_mb']:.1f}MB VMS={info['process_vms_mb']:.1f}MB ({info['process_percent']:.1f}%)"
        )
        self.logger.info(
            f"System: {info['system_used_gb']:.1f}GB/{info['system_total_gb']:.1f}GB ({info['system_percent']:.1f}%) Available={info['system_available_gb']:.1f}GB"
        )
        self.logger.info(
            f"Swap: {info['swap_used_gb']:.1f}GB/{info['swap_total_gb']:.1f}GB ({info['swap_percent']:.1f}%)"
        )
        self.logger.info(
            f"GC: Gen0={info['gc_gen0']} Gen1={info['gc_gen1']} Gen2={info['gc_gen2']}"
        )
        if info["memory_limit_mb"]:
            self.logger.info(f"Memory Limit: {info['memory_limit_mb']:.1f}MB")
        self.logger.info(f"Peak Process Memory: {self.peak_memory:.1f}MB")

        # Force flush to ensure we don't lose data on crash
        for handler in self.logger.handlers:
            handler.flush()

        return info

    def start_monitoring(self):
        """Start continuous memory monitoring in background thread."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        self.logger.info("Memory monitoring started")

    def stop_monitoring(self):
        """Stop memory monitoring."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        self.logger.info("Memory monitoring stopped")

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.running:
            try:
                info = self.get_memory_info()
                self.measurements.append(info)

                # Log significant changes
                if len(self.measurements) > 1:
                    prev = self.measurements[-2]
                    current = self.measurements[-1]

                    rss_change = current["process_rss_mb"] - prev["process_rss_mb"]
                    if abs(rss_change) > 10:  # Log changes > 10MB
                        self.logger.info(
                            f"Memory change: RSS {rss_change:+.1f}MB (now {current['process_rss_mb']:.1f}MB)"
                        )

                # Keep only last 1000 measurements
                if len(self.measurements) > 1000:
                    self.measurements = self.measurements[-1000:]

                time.sleep(self.interval)
            except Exception as e:
                self.logger.error(f"Monitor error: {e}")
                time.sleep(1.0)

    def get_summary(self):
        """Get monitoring summary."""
        if not self.measurements:
            return "No measurements taken"

        first = self.measurements[0]
        last = self.measurements[-1]

        duration = last["timestamp"] - first["timestamp"]
        rss_change = last["process_rss_mb"] - first["process_rss_mb"]

        return f"""
Memory Monitoring Summary:
Duration: {duration:.1f}s
Process RSS: {first["process_rss_mb"]:.1f}MB → {last["process_rss_mb"]:.1f}MB (change: {rss_change:+.1f}MB)
Peak RSS: {self.peak_memory:.1f}MB
System Available: {last["system_available_gb"]:.1f}GB ({100 - last["system_percent"]:.1f}% free)
Swap: {last["swap_percent"]:.1f}% used
"""


def main():
    """Test the memory monitor."""
    monitor = MemoryMonitor(interval=0.5)

    monitor.log_memory_state("STARTUP")
    monitor.start_monitoring()

    try:
        # Simulate some work
        for i in range(10):
            time.sleep(1)
            monitor.log_memory_state(f"ITERATION {i + 1}")
    finally:
        monitor.stop_monitoring()
        print(monitor.get_summary())


if __name__ == "__main__":
    main()
