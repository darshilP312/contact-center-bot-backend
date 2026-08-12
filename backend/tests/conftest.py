"""conftest.py — pytest configuration and shared fixtures."""
import sys
import os

# Ensure the backend app is on the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
