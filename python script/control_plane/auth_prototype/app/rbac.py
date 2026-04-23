from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Permission, Role


@dataclass(frozen=True)
class PermissionDefinition:
    name: str
    description: str


@dataclass(frozen=True)
class RoleDefinition:
    name: str
    description: str
    permission_names: tuple[str, ...]


@dataclass(frozen=True)
class RBACSeedSummary:
    permissions_created: int
    roles_created: int
    roles_updated: int


PERMISSION_DEFINITIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition("audit:read", "Consulter les evenements d'audit."),
    PermissionDefinition("dashboard:read", "Acceder au tableau de bord du control panel."),
    PermissionDefinition("inventory:read", "Lister les routeurs et ordinateurs industriels detectes."),
    PermissionDefinition("inventory:scan", "Declencher une detection ou un scan d'inventaire."),
    PermissionDefinition("provision:prepare", "Preparer un dossier de provisionnement."),
    PermissionDefinition("provision:run", "Lancer un provisionnement distant."),
    PermissionDefinition("provision:cancel", "Annuler un provisionnement en cours."),
    PermissionDefinition("site:read", "Lire la configuration d'un site."),
    PermissionDefinition("site:write", "Modifier la configuration d'un site."),
    PermissionDefinition("user:read", "Consulter les utilisateurs miroir et leurs roles."),
    PermissionDefinition("user:write", "Activer ou desactiver un utilisateur miroir."),
    PermissionDefinition("role:assign", "Attribuer ou retirer des roles metier."),
)

ROLE_DEFINITIONS: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        name="viewer",
        description="Lecture seule sur les sites et l'inventaire.",
        permission_names=("dashboard:read", "inventory:read", "site:read"),
    ),
    RoleDefinition(
        name="operator",
        description="Operateur standard du control panel.",
        permission_names=("dashboard:read", "inventory:read", "inventory:scan", "site:read"),
    ),
    RoleDefinition(
        name="provisioning_manager",
        description="Operateur habilite a preparer et lancer un provisionnement.",
        permission_names=(
            "dashboard:read",
            "inventory:read",
            "inventory:scan",
            "provision:prepare",
            "provision:run",
            "provision:cancel",
            "site:read",
        ),
    ),
    RoleDefinition(
        name="admin",
        description="Administrateur applicatif avec toutes les permissions du catalogue.",
        permission_names=tuple(definition.name for definition in PERMISSION_DEFINITIONS),
    ),
)


def seed_rbac_catalog(session: Session) -> RBACSeedSummary:
    permissions_by_name = {
        permission.name: permission
        for permission in session.scalars(select(Permission).order_by(Permission.name))
    }
    permissions_created = 0

    for definition in PERMISSION_DEFINITIONS:
        permission = permissions_by_name.get(definition.name)
        if permission is None:
            permission = Permission(name=definition.name, description=definition.description)
            session.add(permission)
            permissions_by_name[definition.name] = permission
            permissions_created += 1
        else:
            permission.description = definition.description

    session.flush()

    roles_by_name = {
        role.name: role
        for role in session.scalars(select(Role).options(selectinload(Role.permissions)).order_by(Role.name))
    }
    roles_created = 0
    roles_updated = 0

    for definition in ROLE_DEFINITIONS:
        role = roles_by_name.get(definition.name)
        if role is None:
            role = Role(name=definition.name, description=definition.description)
            session.add(role)
            roles_by_name[definition.name] = role
            roles_created += 1
        else:
            role.description = definition.description
            roles_updated += 1

        role.permissions = sorted(
            (permissions_by_name[name] for name in definition.permission_names),
            key=lambda permission: permission.name,
        )

    session.commit()
    return RBACSeedSummary(
        permissions_created=permissions_created,
        roles_created=roles_created,
        roles_updated=roles_updated,
    )


def fetch_rbac_catalog(session: Session) -> dict[str, list[dict[str, object]]]:
    permissions = session.scalars(select(Permission).order_by(Permission.name)).all()
    roles = session.scalars(select(Role).options(selectinload(Role.permissions)).order_by(Role.name)).all()
    return {
        "permissions": [
            {
                "name": permission.name,
                "description": permission.description,
            }
            for permission in permissions
        ],
        "roles": [
            {
                "name": role.name,
                "description": role.description,
                "permissions": sorted(permission.name for permission in role.permissions),
            }
            for role in roles
        ],
    }


def role_names_have_permission(
    session: Session,
    role_names: Iterable[str],
    permission_name: str,
) -> bool:
    requested_roles = tuple(sorted(set(role_names)))
    if not requested_roles:
        return False

    statement = (
        select(Permission.name)
        .join(Permission.roles)
        .where(Role.name.in_(requested_roles), Permission.name == permission_name)
        .limit(1)
    )
    return session.scalar(statement) is not None
