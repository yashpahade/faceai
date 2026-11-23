"""
ONNX Runtime session creation with GPU -> CPU fallback.

ONNX kya hai? Model ka framework-independent format. PyTorch/TF mein train karo, .onnx export karo,
phir ONNX Runtime se kahin bhi chalao (CPU, CUDA, TensorRT, mobile). Production serving ka standard.

"Execution provider" = kis hardware pe chalega. Hum list dete hain priority order mein;
ORT pehla available wala use karta hai.
"""

import logging
import os
import sys
import sysconfig
from pathlib import Path

import onnxruntime as ort

logger = logging.getLogger(__name__)

_dlls_preloaded = False


def _add_nvidia_dll_dirs() -> None:
    """
    pip wale nvidia-* packages ke `bin` folders ko Windows DLL search path mein daalo.
    `ort.preload_dlls()` sirf main DLLs load karta hai; cuDNN 9 apni sub-libraries
    (e.g. cudnn_engines_*64_9.dll) baad mein naam se dhoondhta hai -> folder search path pe na ho
    to CUDNN_STATUS_SUBLIBRARY_LOADING_FAILED aur chupchaap CPU fallback.
    """
    if sys.platform != "win32":
        return
    nvidia_root = Path(sysconfig.get_paths()["purelib"]) / "nvidia"
    for bin_dir in sorted(nvidia_root.glob("*/bin")):
        os.add_dll_directory(str(bin_dir))
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def _preload_cuda_dlls() -> None:
    """Windows pe pip se aaye nvidia-* (CUDA/cuDNN) DLLs ko load karo. Ek hi baar."""
    global _dlls_preloaded
    if not _dlls_preloaded and hasattr(ort, "preload_dlls"):
        try:
            _add_nvidia_dll_dirs()
            ort.preload_dlls()
        except Exception as e:  # CUDA libs nahi hain -> CPU fallback chalega
            logger.warning("CUDA DLL preload failed: %s", e)
        _dlls_preloaded = True


def resolve_providers(device: str) -> list[str]:
    available = ort.get_available_providers()
    if device == "cpu":
        return ["CPUExecutionProvider"]
    if "CUDAExecutionProvider" in available:
        _preload_cuda_dlls()
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if device == "cuda":
        raise RuntimeError(f"device=cuda requested but CUDA provider unavailable: {available}")
    return ["CPUExecutionProvider"]


def create_session(
    model_path: Path, device: str = "auto", intra_op_threads: int = 0
) -> ort.InferenceSession:
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}. Run: python -m faceai.models.download"
        )
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    opts.log_severity_level = 3  # sirf errors
    if intra_op_threads:
        # CPU: kai requests ek saath => har session saare cores na maange (oversubscription)
        opts.intra_op_num_threads = intra_op_threads
    session = ort.InferenceSession(
        str(model_path), sess_options=opts, providers=resolve_providers(device)
    )
    if device == "cuda":
        session.disable_fallback()  # GPU maanga hai to silent CPU fallback nahi, error do
    logger.info(
        "loaded %s on %s",
        model_path.name,
        session.get_providers()[0],
        extra={"model": model_path.name, "provider": session.get_providers()[0]},
    )
    return session
