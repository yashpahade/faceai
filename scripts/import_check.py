import importlib, sys
from pathlib import Path

# Ensure project root is on sys.path so `backend` package can be imported
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

modules=['backend.services.pipeline','backend.services.feature_extractor','backend.services.faiss_service','backend.services.face_detector']
for m in modules:
    try:
        importlib.import_module(m)
        print('OK',m)
    except Exception as e:
        print('ERR',m,':',e)
