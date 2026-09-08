"""Governed extension namespace.

Core modules must never import optional implementation dependencies from this
namespace during package import. Extensions are installed, enabled, and tested
independently after their blueprint gates pass.
"""

EXTENSION_IDS = (
    "wake_word",
    "voice_power",
    "lan_dashboard",
    "bluetooth",
)

__all__ = ["EXTENSION_IDS"]
