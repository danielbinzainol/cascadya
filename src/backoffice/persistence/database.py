import os
from urllib.parse import quote_plus

import hvac
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from pathlib import Path

load_dotenv()


class DatabaseConfigError(RuntimeError):
    """Raised when the database URL cannot be resolved safely."""


def _build_database_url_from_parts(*, password: str) -> str:
    user = os.getenv("DATABASE_USERNAME", "postgres")
    host = os.getenv("DATABASE_HOST")
    port = os.getenv("DATABASE_PORT", "5432")
    db_name = os.getenv("DATABASE_NAME", "forecast_database")
    driver = os.getenv("DATABASE_DRIVER", "postgresql+psycopg")
    encoded_user = quote_plus(user)
    encoded_password = quote_plus(password)
    return f"{driver}://{encoded_user}:{encoded_password}@{host}:{port}/{db_name}"


def _vault_is_configured() -> bool:
    return bool(os.getenv("VAULT_ADDR") and os.getenv("PSQL_VAULT_SECRET_PATH"))


def _read_psql_vault_token() -> str | None:
    psql_token_file = os.getenv("PSQL_VAULT_TOKEN_FILE")
    if psql_token_file:
        content = Path(psql_token_file).read_text(encoding="utf-8").strip()
        return content or None
    return None


def _read_password_from_vault() -> str | None:
    """Return DB password from Vault or None when Vault is not configured."""
    if not _vault_is_configured():
        return None

    vault_addr = os.getenv("VAULT_ADDR")
    psql_vault_token = _read_psql_vault_token()
    vault_role_id = os.getenv("VAULT_ROLE_ID")
    vault_secret_id = os.getenv("VAULT_SECRET_ID")
    psql_vault_secret_path = os.getenv("PSQL_VAULT_SECRET_PATH")
    mount = "secret"
    field = "POSTGRES_PASSWORD"
    verify_tls = True

    try:
        client = hvac.Client(url=vault_addr, verify=verify_tls)
        if psql_vault_token:
            client.token = psql_vault_token
        elif vault_role_id and vault_secret_id:
            auth = client.auth.approle.login(
                role_id=vault_role_id,
                secret_id=vault_secret_id,
            )
            client.token = auth["auth"]["client_token"]
        else:
            raise DatabaseConfigError(
                "Vault is configured but no authentication method is set. "
                "Provide PSQL_VAULT_TOKEN_FILE or (VAULT_ROLE_ID and VAULT_SECRET_ID)."
            )

        if not client.is_authenticated():
            raise DatabaseConfigError(
                "Vault authentication failed for database secret."
            )

        response = client.secrets.kv.v2.read_secret_version(
            mount_point=mount,
            path=psql_vault_secret_path,
        )
        secret_data = response.get("data", {}).get("data", {})
        password = secret_data.get(field)
        if not password:
            raise DatabaseConfigError(
                f"Vault secret '{psql_vault_secret_path}' is missing expected field '{field}'."
            )
        return str(password)
    except DatabaseConfigError:
        raise
    except Exception as exc:  # pragma: no cover - provider/network specific
        raise DatabaseConfigError(
            "Vault lookup for database credentials failed."
        ) from exc


def build_database_url() -> str:
    """Resolve database URL with precedence: Vault > env URL > env parts."""
    vault_password = _read_password_from_vault()
    if vault_password:
        return _build_database_url_from_parts(password=vault_password)

    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    env_password = os.getenv("POSTGRES_PASSWORD")
    if env_password:
        return _build_database_url_from_parts(password=env_password)

    raise DatabaseConfigError(
        "Database configuration is missing. Set Vault config (VAULT_ADDR + "
        "PSQL_VAULT_SECRET_PATH), or DATABASE_URL, or DB parts including password."
    )


engine = create_engine(build_database_url())
_query_engine: Engine | None = None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_query_engine() -> Engine:
    """Return engine used by read-only query API."""
    global _query_engine
    if _query_engine is not None:
        return _query_engine
    query_url = os.getenv("DATABASE_QUERY_URL") or os.getenv("DATABASE_URL")
    if query_url:
        _query_engine = create_engine(query_url)
        return _query_engine
    _query_engine = create_engine(build_database_url())
    return _query_engine
