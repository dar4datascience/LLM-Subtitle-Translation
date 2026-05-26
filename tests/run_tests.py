#!/usr/bin/env python3
"""
Run all unit tests for LLM Subtitle Translation toolkit.

Usage:
    python tests/run_tests.py
    python tests/run_tests.py -v  # verbose
"""
import unittest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Discover and run all tests
if __name__ == '__main__':
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2 if '-v' in sys.argv else 1)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)
