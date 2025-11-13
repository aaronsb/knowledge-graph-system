"""
Device Selection for Embedding Models - Cross-Platform Support.

Provides unified device detection for both text and vision embedding models.
Handles CUDA (NVIDIA), MPS (Apple Silicon/ARM), and CPU fallback.

Architecture:
- MPS (Metal Performance Shaders): Explicit detection for Apple Silicon and ARM platforms
- CUDA: Auto-detected by PyTorch (NVIDIA GPUs on Linux/Windows)
- CPU: Automatic fallback when no GPU available

Usage:
    from api.lib.device_selector import get_best_device

    device = get_best_device()
    # Returns: "mps", "cuda", or "cpu"
"""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

DeviceType = Literal["mps", "cuda", "cpu"]


def get_best_device(prefer_cpu: bool = False) -> DeviceType:
    """
    Detect the best available device for embedding model inference.

    Device selection priority:
    1. MPS (Metal Performance Shaders) - Apple Silicon M1/M2/M3 and other ARM platforms
    2. CUDA - NVIDIA GPUs (Linux/Windows)
    3. CPU - Fallback when no GPU available

    Args:
        prefer_cpu: Force CPU even if GPU available (useful for testing or resource management)

    Returns:
        Device string: "mps", "cuda", or "cpu"

    Examples:
        # Auto-detect best device
        device = get_best_device()

        # Force CPU (for testing or when GPU is busy)
        device = get_best_device(prefer_cpu=True)
    """
    if prefer_cpu:
        logger.info("🖥️  CPU explicitly requested")
        return "cpu"

    try:
        import torch

        # Check for MPS (Apple Silicon / ARM platforms)
        # MPS must be checked BEFORE CUDA because torch.cuda.is_available()
        # may return false positives on some ARM systems
        if torch.backends.mps.is_available():
            # Verify MPS actually works with a small tensor operation
            try:
                test_tensor = torch.zeros(1, device="mps")
                test_tensor.cpu()  # Force synchronization
                logger.info("🍎 MPS (Metal Performance Shaders) detected and verified - Using Apple GPU")
                return "mps"
            except Exception as e:
                logger.warning(f"⚠️  MPS available but not usable: {e} - Falling back to next available device")
                # Continue to CUDA check, then CPU

        # Check for CUDA (NVIDIA GPUs)
        if torch.cuda.is_available():
            # Get GPU info for logging
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"🎮 CUDA GPU detected - {gpu_name} ({vram_gb:.1f}GB VRAM)")
            return "cuda"

        # Fallback to CPU
        logger.info("🖥️  No GPU detected - Using CPU")
        return "cpu"

    except ImportError:
        logger.warning("⚠️  PyTorch not available - Defaulting to CPU")
        return "cpu"
    except Exception as e:
        logger.warning(f"⚠️  Device detection failed: {e} - Defaulting to CPU")
        return "cpu"


def get_device_info() -> dict:
    """
    Get detailed information about the current device configuration.

    Returns:
        Dict with:
        - 'device': Selected device ("mps", "cuda", or "cpu")
        - 'device_name': Human-readable device name
        - 'vram_available_mb': Available VRAM in MB (0 for CPU/MPS)
        - 'vram_total_mb': Total VRAM in MB (0 for CPU/MPS)
        - 'supports_half_precision': Whether FP16 is supported

    Examples:
        info = get_device_info()
        print(f"Using {info['device']}: {info['device_name']}")
        if info['vram_total_mb'] > 0:
            print(f"VRAM: {info['vram_total_mb']}MB")
    """
    device = get_best_device()

    result = {
        'device': device,
        'device_name': 'Unknown',
        'vram_available_mb': 0,
        'vram_total_mb': 0,
        'supports_half_precision': False
    }

    try:
        import torch

        if device == "mps":
            result['device_name'] = 'Apple Metal GPU (MPS)'
            result['supports_half_precision'] = True  # MPS supports FP16
            # Note: MPS doesn't expose VRAM info via PyTorch API

        elif device == "cuda":
            result['device_name'] = torch.cuda.get_device_name(0)
            result['supports_half_precision'] = True  # Modern CUDA GPUs support FP16

            # Get VRAM info
            vram_free, vram_total = torch.cuda.mem_get_info(0)
            result['vram_available_mb'] = int(vram_free / 1024**2)
            result['vram_total_mb'] = int(vram_total / 1024**2)

        else:  # cpu
            import platform
            result['device_name'] = f"CPU ({platform.processor() or 'Unknown'})"
            result['supports_half_precision'] = False  # CPU generally slower with FP16

    except Exception as e:
        logger.warning(f"Failed to get device info: {e}")

    return result


def check_device_health() -> dict:
    """
    Health check for device configuration.

    Returns:
        Dict with:
        - 'status': 'healthy' or 'degraded'
        - 'device': Current device
        - 'warnings': List of warning messages
        - 'info': Device info dict

    Examples:
        health = check_device_health()
        if health['status'] == 'degraded':
            for warning in health['warnings']:
                print(f"Warning: {warning}")
    """
    device = get_best_device()
    info = get_device_info()
    warnings = []

    # Check for common issues
    try:
        import torch

        if device == "cuda":
            # Check VRAM availability
            vram_free = info['vram_available_mb']
            if vram_free < 500:
                warnings.append(
                    f"Low VRAM: {vram_free}MB free. "
                    "Embeddings may be slow or fail. Consider using CPU mode."
                )

        elif device == "mps":
            # Check MPS functionality with a small operation
            try:
                test_tensor = torch.randn(10, 10, device="mps")
                result = test_tensor @ test_tensor.T
                result.cpu()  # Force synchronization
            except Exception as e:
                warnings.append(
                    f"MPS device selected but operations failing: {e}. "
                    "Consider forcing CPU mode or updating macOS/PyTorch."
                )

            # Check macOS version (MPS requires macOS 12.3+)
            try:
                import platform
                mac_version = platform.mac_ver()[0]
                if mac_version:
                    version_parts = tuple(map(int, mac_version.split('.')[:2]))
                    if version_parts < (12, 3):
                        warnings.append(
                            f"macOS {mac_version} may have limited MPS support. "
                            "Recommended: macOS 12.3 or later for best performance."
                        )
            except Exception as version_check_error:
                # Don't fail health check if version detection fails
                pass

        elif device == "cpu":
            # Check if CUDA was expected but unavailable
            if torch.cuda.is_available():
                warnings.append(
                    "CUDA is available but not being used. "
                    "Check device selection logic."
                )

            # Check if MPS was expected but unavailable
            if torch.backends.mps.is_available():
                warnings.append(
                    "MPS is available but not being used. "
                    "Check device selection logic."
                )

    except Exception as e:
        warnings.append(f"Device health check incomplete: {e}")

    status = 'healthy' if len(warnings) == 0 else 'degraded'

    return {
        'status': status,
        'device': device,
        'warnings': warnings,
        'info': info
    }


def log_device_selection(model_name: str):
    """
    Log device selection for a specific model.

    Useful for debugging and monitoring which device is being used.

    Args:
        model_name: Name of the model being loaded

    Examples:
        log_device_selection("nomic-ai/nomic-embed-text-v1.5")
    """
    info = get_device_info()
    device = info['device']
    device_name = info['device_name']

    logger.info(f"📍 Loading {model_name}")
    logger.info(f"   Device: {device} ({device_name})")

    if device == "cuda":
        vram_total = info['vram_total_mb']
        vram_avail = info['vram_available_mb']
        logger.info(f"   VRAM: {vram_avail}MB free / {vram_total}MB total")

    if info['supports_half_precision']:
        logger.info(f"   FP16 supported: Yes")
