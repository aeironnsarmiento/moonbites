from __future__ import annotations

from unittest.mock import patch

from backend.scripts import admins


class _AdminTable:
    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows or []
        self.upserts: list[dict] = []
        self.deleted_email: str | None = None

    def upsert(self, payload: dict, on_conflict: str):
        assert on_conflict == "email"
        self.upserts.append(payload)
        return self

    def delete(self):
        return self

    def select(self, _columns: str):
        return self

    def eq(self, _column: str, value: str):
        self.deleted_email = value
        return self

    def order(self, _column: str):
        return self

    def execute(self):
        return type("Response", (), {"data": self.rows})()


class _AdminClient:
    def __init__(self, table: _AdminTable):
        self.admin_table = table

    def table(self, table_name: str):
        assert table_name == "recipe_admins"
        return self.admin_table


def test_grant_admin_lowercases_and_upserts_email(capsys):
    table = _AdminTable()

    with patch("backend.scripts.admins.get_supabase_client", return_value=_AdminClient(table)):
        exit_code = admins.main(["grant", "ADMIN@Example.COM"])

    assert exit_code == 0
    assert table.upserts == [{"email": "admin@example.com"}]
    assert "Granted admin: admin@example.com" in capsys.readouterr().out


def test_revoke_admin_deletes_email(capsys):
    table = _AdminTable()

    with patch("backend.scripts.admins.get_supabase_client", return_value=_AdminClient(table)):
        exit_code = admins.main(["revoke", "ADMIN@Example.COM"])

    assert exit_code == 0
    assert table.deleted_email == "admin@example.com"
    assert "Revoked admin: admin@example.com" in capsys.readouterr().out


def test_list_admins_prints_sorted_rows(capsys):
    table = _AdminTable(
        [
            {"email": "first@example.com"},
            {"email": "second@example.com"},
        ]
    )

    with patch("backend.scripts.admins.get_supabase_client", return_value=_AdminClient(table)):
        exit_code = admins.main(["list"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "first@example.com" in output
    assert "second@example.com" in output
