"""Independent, auditable reconstruction of the 2026 CT steganography paper."""

from .config import ExperimentConfig
from .encryption import decrypt_secret, encrypt_secret
from .methods import available_methods, build_method, register_method
from .pipeline import ExtractionResult, StegoResult, embed_secret, extract_secret
from .digital_ad import DigitalADConfig

__all__ = [
    "ExperimentConfig",
    "DigitalADConfig",
    "ExtractionResult",
    "StegoResult",
    "available_methods",
    "build_method",
    "decrypt_secret",
    "embed_secret",
    "encrypt_secret",
    "extract_secret",
    "register_method",
]

__version__ = "0.3.0"
