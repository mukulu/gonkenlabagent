"""Authoritative product identity for active package code."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProductIdentity:
    """Stable names used by CLI, logs, prompts, and future runtime surfaces."""

    package_name: str
    product_name: str
    spoken_name: str
    service_name: str


IDENTITY = ProductIdentity(
    package_name="gonkenlab-agent",
    product_name="GonKenLab Agent",
    spoken_name="GonKenLab",
    service_name="gonken-agent",
)
