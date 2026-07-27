"""Deterministic digital A+D steganography research path.

This package is intentionally independent from the audited paper path in
``ctsteg.pipeline``.  AP/GP/HP preprocessing is not imported or reused here.
"""

from .config import DigitalADConfig
from .types import MethodId

__all__ = ["DigitalADConfig", "MethodId"]
