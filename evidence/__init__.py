"""Version control for science done by AI agents."""

from .errors import EvidenceError
from .store import Store

__all__ = ["EvidenceError", "Store"]
__version__ = "0.2.0"
