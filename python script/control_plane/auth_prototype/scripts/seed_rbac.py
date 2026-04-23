from __future__ import annotations

from auth_prototype.app.database import SessionLocal, database_is_healthy
from auth_prototype.app.rbac import seed_rbac_catalog


def main() -> int:
    with SessionLocal() as session:
        if not database_is_healthy(session):
            print("Database unavailable.")
            return 1

        summary = seed_rbac_catalog(session)

    print("RBAC seed completed.")
    print(f"permissions_created={summary.permissions_created}")
    print(f"roles_created={summary.roles_created}")
    print(f"roles_updated={summary.roles_updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
