"""SQLAlchemy ORM models. One class per entity in the Phase 1 schema
(product brief §24). Import this module (or any symbol from it) before
calling Base.metadata.create_all / running Alembic autogenerate, so every
model is registered on Base.metadata.
"""

from app.db.base import Base
from app.models.application import Application
from app.models.audit import AuditLog
from app.models.conversation import Conversation, Message
from app.models.device import Device, DeviceCapability, DevicePermission
from app.models.integration import Integration
from app.models.memory import Memory, Workflow
from app.models.setting import SystemSetting
from app.models.task import Task, TaskStep
from app.models.tool import Permission, PermissionGrant, Tool
from app.models.user import User

__all__ = [
    "Application",
    "AuditLog",
    "Base",
    "Conversation",
    "Device",
    "DeviceCapability",
    "DevicePermission",
    "Integration",
    "Memory",
    "Message",
    "Permission",
    "PermissionGrant",
    "SystemSetting",
    "Task",
    "TaskStep",
    "Tool",
    "User",
    "Workflow",
]
