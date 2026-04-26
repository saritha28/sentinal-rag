"""Repository layer.

Repositories own all SQL access for a given aggregate. Services compose
repositories; routes never touch the DB directly.

Phase 1 ships:
    - tenants   (writes are admin-only; reads are scoped)
    - users
    - roles + permissions
"""

from app.db.repositories.base import BaseRepository
from app.db.repositories.permissions import PermissionRepository
from app.db.repositories.roles import RoleRepository
from app.db.repositories.tenants import TenantRepository
from app.db.repositories.users import UserRepository

__all__ = [
    "BaseRepository",
    "PermissionRepository",
    "RoleRepository",
    "TenantRepository",
    "UserRepository",
]
