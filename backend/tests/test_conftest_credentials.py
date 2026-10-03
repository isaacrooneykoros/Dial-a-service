"""The test harness reads role credentials from database URLs (conftest.py).

Regression: CI's local Postgres URLs have no query string, so django-environ
gives no OPTIONS; the harness must still merge an empty mapping.
"""

import pytest

from conftest import _credentials


@pytest.mark.parametrize(
    ("url", "options"),
    [
        ("postgres://dial_app:secret@localhost:5432/dialaservice", {}),
        (
            "postgresql://dial_app:secret@ep-x-pooler.eu-central-1.aws.neon.tech/db?sslmode=require",
            {"sslmode": "require"},
        ),
    ],
)
def test_options_are_always_a_mapping(url: str, options: dict[str, str]) -> None:
    credentials = _credentials(url)
    assert credentials["OPTIONS"] == options
    assert credentials["USER"] == "dial_app"


def test_neon_pooled_hosts_become_direct() -> None:
    credentials = _credentials("postgres://u:p@ep-x-pooler.eu-central-1.aws.neon.tech/db")
    assert credentials["HOST"] == "ep-x.eu-central-1.aws.neon.tech"
