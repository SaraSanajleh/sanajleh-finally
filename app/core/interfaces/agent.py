"""Agent abstraction for future multi-agent orchestration."""
#"طبقة تجريد للوكلاء (Agents) من أجل دعم تنسيق وإدارة عدة وكلاء (Multi-Agent Orchestration) في المستقبل."

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

#Protocol هو العقد عشان  أي Agent يجب أن يحقق هذه المواصفات.

@runtime_checkable
class PackageAgent(Protocol):  # "إذا أردت أن يكون لديك Agent مسؤول عن إنشاء الباقات السياحية، فيجب أن يلتزم بهذه القواعد."
    """Contract for agents that generate tourism packages."""

    async def generate_package(self, request: Any) -> Any:  # request هو طلب المستخدم 
        """Transform a validated package request into a tourism package."""
        ...
