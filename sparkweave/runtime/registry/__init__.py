"""Runtime registries for NG-owned compatibility entry points."""

from .capability_registry import CapabilityRegistry, get_capability_registry

__all__ = ["CapabilityRegistry", "get_capability_registry"]
