import sys
import os

try:
    import dotenv
    print("dotenv import successful from:", dotenv.__file__)
except ImportError as e:
    print("dotenv import failed:", e)
