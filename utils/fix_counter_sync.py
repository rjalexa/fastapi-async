#!/usr/bin/env python3
"""
DEPRECATED: Utility script to fix Redis counter synchronization issues.

This script is deprecated as the metrics counter system has been removed.
Use the cleanup_metrics.py script to remove any remaining metrics keys.
"""

import sys


def main():
    print("⚠️  DEPRECATED: This script is no longer needed.")
    print("📝 The metrics counter system has been removed from the application.")
    print(
        "🧹 Use 'python utils/cleanup_metrics.py' to remove any remaining metrics keys."
    )
    print("ℹ️  Task states are now calculated dynamically by scanning actual tasks.")
    sys.exit(0)


if __name__ == "__main__":
    main()
