"""
Performance profiling utilities for debugging slow operations.
"""

import time
import functools
from typing import Callable
from collections import defaultdict

# Global storage for timing data
_timing_data = defaultdict(lambda: {"count": 0, "total_time": 0.0, "calls": []})
_profiling_enabled = True


def enable_profiling():
    """Enable performance profiling."""
    global _profiling_enabled
    _profiling_enabled = True


def disable_profiling():
    """Disable performance profiling."""
    global _profiling_enabled
    _profiling_enabled = False


def clear_profiling_data():
    """Clear all collected profiling data."""
    global _timing_data
    _timing_data.clear()


def profile(func: Callable) -> Callable:
    """
    Decorator to profile function execution time.

    Usage:
        @profile
        def my_function():
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not _profiling_enabled:
            return func(*args, **kwargs)

        func_name = f"{func.__module__}.{func.__qualname__}"
        start_time = time.perf_counter()

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = time.perf_counter()
            elapsed = end_time - start_time

            _timing_data[func_name]["count"] += 1
            _timing_data[func_name]["total_time"] += elapsed
            _timing_data[func_name]["calls"].append(elapsed)

    return wrapper


def get_profiling_report(sort_by="total", top_n=None) -> str:
    """
    Get a formatted profiling report.

    Args:
        sort_by: Sort by 'total' time, 'average' time, or 'count'
        top_n: Show only top N results (None = show all)

    Returns:
        Formatted string report
    """
    if not _timing_data:
        return "No profiling data collected."

    # Prepare data for sorting
    report_data = []
    for func_name, data in _timing_data.items():
        avg_time = data["total_time"] / data["count"] if data["count"] > 0 else 0
        report_data.append({
            "name": func_name,
            "count": data["count"],
            "total": data["total_time"],
            "average": avg_time,
            "min": min(data["calls"]) if data["calls"] else 0,
            "max": max(data["calls"]) if data["calls"] else 0,
        })

    # Sort data
    if sort_by == "total":
        report_data.sort(key=lambda x: x["total"], reverse=True)
    elif sort_by == "average":
        report_data.sort(key=lambda x: x["average"], reverse=True)
    elif sort_by == "count":
        report_data.sort(key=lambda x: x["count"], reverse=True)

    # Limit to top N
    if top_n:
        report_data = report_data[:top_n]

    # Format report
    lines = [
        "=" * 100,
        "PERFORMANCE PROFILING REPORT",
        "=" * 100,
        f"{'Function':<50} {'Calls':<8} {'Total (s)':<12} {'Avg (s)':<12} {'Min (s)':<12} {'Max (s)':<12}",
        "-" * 100,
    ]

    for item in report_data:
        lines.append(
            f"{item['name']:<50} {item['count']:<8} "
            f"{item['total']:<12.4f} {item['average']:<12.6f} "
            f"{item['min']:<12.6f} {item['max']:<12.6f}"
        )

    lines.append("=" * 100)

    return "\n".join(lines)


def print_profiling_report(sort_by="total", top_n=20):
    """Print profiling report to console."""
    print(get_profiling_report(sort_by, top_n))


def get_timing_data():
    """Get raw timing data dictionary."""
    return dict(_timing_data)
