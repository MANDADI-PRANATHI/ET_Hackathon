"""Put src/ on the path so tests import `brain.*` without setting PYTHONPATH."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
