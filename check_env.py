import sys
import os
print(f"Executable: {sys.executable}")
print(f"Version: {sys.version}")
print(f"Path: {sys.path}")
try:
    import jinja2
    print(f"Jinja2: {jinja2.__file__}")
except ImportError:
    print("Jinja2: NOT FOUND")
