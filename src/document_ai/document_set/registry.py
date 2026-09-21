# -*- coding: utf-8 -*-
"""Default DomainPack registry factory."""

from __future__ import annotations

from document_ai.document_set.domain_pack import DomainPackRegistry


def build_default_pack_registry() -> DomainPackRegistry:
    """Register built-in domain packs (lazy import to avoid cycles)."""
    from document_ai.domain_packs.ec_sw.pack import EcSwDomainPack

    reg = DomainPackRegistry()
    reg.register(EcSwDomainPack())
    return reg
