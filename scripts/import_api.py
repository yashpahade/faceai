import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import backend.api as api
    print('OK backend.api')
except Exception as e:
    print('ERR backend.api:', e)
