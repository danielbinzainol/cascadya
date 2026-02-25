import pytest
from fastapi import HTTPException

from app import resolve_market_orders_csv_path


@pytest.mark.parametrize(
    "project",
    [
        "",
        "inariz!",
        "inariz test",
        "inariz/test",
        "../secret",
        "énergie",
    ],
    ids=[
        "empty",
        "special-char",
        "space",
        "slash",
        "path-traversal",
        "non-ascii",
    ],
)
def test_resolve_market_orders_csv_path_rejects_invalid_project(project: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        resolve_market_orders_csv_path(project, "20260211_20260223_1735")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid project format."


@pytest.mark.parametrize(
    "file_id",
    [
        "",
        "20260211-20260223-1735",   # mauvais séparateurs
        "20260211_20260223",        # heure manquante
        "20260211_20260223_173",    # HHMM incomplet
        "20260211_20260223_17AA",   # non numérique
        "26_02_11_20260223_1735",   # format date invalide
    ],
    ids=[
        "empty",
        "wrong-separators",
        "missing-time",
        "short-time",
        "non-numeric-time",
        "wrong-date-format",
    ],
)
def test_resolve_market_orders_csv_path_rejects_invalid_file_id(file_id: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        resolve_market_orders_csv_path("inariz", file_id)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid file_id format. Expected YYYYMMDD_YYYYMMDD_HHMM."
