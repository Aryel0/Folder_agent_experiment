import unittest
import sys
import os

if __name__ == "__main__":
    # Ensure the root directory is in the python path
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if not result.wasSuccessful():
        sys.exit(1)
