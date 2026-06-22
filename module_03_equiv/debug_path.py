import os
import sys

print(f"Current Working Directory: {os.getcwd()}")
print(f"Python Path: {sys.path}")

try:
    import nlp_utils
    print("Successfully imported nlp_utils")
except ImportError as e:
    print(f"Failed to import nlp_utils: {e}")

try:
    import src.nlp_utils
    print("Successfully imported src.nlp_utils")
except ImportError as e:
    print(f"Failed to import src.nlp_utils: {e}")
