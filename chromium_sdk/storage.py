"""SQLite persistence layer.

Holds two tables: ``environments`` and ``proxies``. The fingerprint is stored
as a JSON blob on each environment, so an environment is fully self-describing.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

_SCHEMA = """
CREATE TABLE IF NOT EXISTS environments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    platform        TEXT NOT NULL DEFAULT 'Win32',
    browser_version TEXT,
    user_agent      TEXT,
    proxy_code      TEXT,
    proxy_mode      TEXT NOT NULL DEFAULT 'no_proxy',
    custom_proxy_type     TEXT,
    custom_proxy_addr     TEXT,
    custom_proxy_port     INTEGER,
    custom_proxy_username TEXT,
    custom_proxy_password TEXT,
    open_home_page  INTEGER NOT NULL DEFAULT 0,
    enable_tabs     INTEGER NOT NULL DEFAULT 0,
    tabs            TEXT NOT NULL DEFAULT '',
    sync_user_info  INTEGER NOT NULL DEFAULT 0,
    cookie          TEXT NOT NULL DEFAULT '',
    launch_args     TEXT NOT NULL DEFAULT '',
    remark          TEXT NOT NULL DEFAULT '',
    tag_ids         TEXT NOT NULL DEFAULT '[]',
    fingerprint     TEXT NOT NULL DEFAULT '{}',
    pid             INTEGER,
    debug_port      INTEGER,
    create_time     TEXT NOT NULL,
    update_time     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proxies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT UNIQUE NOT NULL,
    proxy_name  TEXT NOT NULL,
    proxy_type  TEXT NOT NULL,
    proxy_addr  TEXT NOT NULL,
    proxy_port  INTEGER NOT NULL,
    username    TEXT NOT NULL DEFAULT '',
    password    TEXT NOT NULL DEFAULT '',
    remark      TEXT NOT NULL DEFAULT '',
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS browser_errors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL,
    detail      TEXT,
    type        TEXT,
    create_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

# Columns whose stored value is JSON-encoded.
_JSON_COLUMNS = {"tag_ids", "fingerprint"}


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def new_code() -> str:
    """32-char hex identifier, mirroring the md5-style codes used by the backend."""
    return secrets.token_hex(16)


# Columns added after the initial schema (ALTER TABLE for existing DBs).
_ENV_MIGRATIONS = (
    ("proxy_mode", "TEXT NOT NULL DEFAULT 'no_proxy'"),
    ("custom_proxy_type", "TEXT"),
    ("custom_proxy_addr", "TEXT"),
    ("custom_proxy_port", "INTEGER"),
    ("custom_proxy_username", "TEXT"),
    ("custom_proxy_password", "TEXT"),
)


class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(environments)").fetchall()
        }
        added_proxy_mode = False
        for name, decl in _ENV_MIGRATIONS:
            if name not in cols:
                self._conn.execute(
                    f"ALTER TABLE environments ADD COLUMN {name} {decl}"
                )
                if name == "proxy_mode":
                    added_proxy_mode = True
        # One-shot: legacy rows that only had proxy_code → existing mode
        if added_proxy_mode:
            self._conn.execute(
                "UPDATE environments SET proxy_mode = 'existing' "
                "WHERE proxy_code IS NOT NULL AND proxy_code != ''"
            )

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        data = dict(row)
        for col in _JSON_COLUMNS:
            if col in data and isinstance(data[col], str):
                try:
                    data[col] = json.loads(data[col])
                except (ValueError, TypeError):
                    data[col] = None
        return data

    # -- environments ---------------------------------------------------------
    def insert_environment(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            code = new_code()
            now = _now()
            record = {
                "code": code,
                "name": fields["name"],
                "platform": fields.get("platform", "Win32"),
                "browser_version": fields.get("browser_version"),
                "user_agent": fields.get("user_agent"),
                "proxy_code": fields.get("proxy_code"),
                "proxy_mode": fields.get("proxy_mode") or "no_proxy",
                "custom_proxy_type": fields.get("custom_proxy_type"),
                "custom_proxy_addr": fields.get("custom_proxy_addr"),
                "custom_proxy_port": fields.get("custom_proxy_port"),
                "custom_proxy_username": fields.get("custom_proxy_username"),
                "custom_proxy_password": fields.get("custom_proxy_password"),
                "open_home_page": int(bool(fields.get("open_home_page", False))),
                "enable_tabs": int(bool(fields.get("enable_tabs", False))),
                "tabs": fields.get("tabs", ""),
                "sync_user_info": int(bool(fields.get("sync_user_info", False))),
                "cookie": fields.get("cookie", ""),
                "launch_args": fields.get("launch_args", ""),
                "remark": fields.get("remark", ""),
                "tag_ids": json.dumps(fields.get("tag_ids", [])),
                "fingerprint": json.dumps(fields.get("fingerprint", {})),
                "create_time": now,
                "update_time": now,
            }
            cols = ", ".join(record.keys())
            ph = ", ".join("?" for _ in record)
            self._conn.execute(
                f"INSERT INTO environments ({cols}) VALUES ({ph})", list(record.values())
            )
            self._conn.commit()
            return self.get_environment(code)  # type: ignore[return-value]

    def get_environment(self, code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM environments WHERE code = ?", (code,)
            ).fetchone()
            return self._row_to_dict(row)

    def list_environments(
        self, page: int = 1, page_size: int = 20, keyword: str = ""
    ) -> Tuple[List[Dict[str, Any]], int]:
        with self._lock:
            where, params = "", []
            if keyword:
                where = "WHERE name LIKE ? OR remark LIKE ? OR code LIKE ?"
                like = f"%{keyword}%"
                params = [like, like, like]
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM environments {where}", params
            ).fetchone()[0]
            offset = max(page - 1, 0) * page_size
            rows = self._conn.execute(
                f"SELECT * FROM environments {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()
            return [self._row_to_dict(r) for r in rows], total  # type: ignore[misc]

    def update_environment(self, code: str, fields: Dict[str, Any]) -> bool:
        allowed = {
            "name", "platform", "browser_version", "user_agent", "proxy_code",
            "proxy_mode", "custom_proxy_type", "custom_proxy_addr",
            "custom_proxy_port", "custom_proxy_username", "custom_proxy_password",
            "open_home_page", "enable_tabs", "tabs", "sync_user_info", "cookie",
            "launch_args", "remark", "tag_ids", "fingerprint", "pid", "debug_port",
        }
        with self._lock:
            sets, params = [], []
            for key, value in fields.items():
                if key not in allowed:
                    continue
                if key in _JSON_COLUMNS:
                    value = json.dumps(value)
                elif key in {"open_home_page", "enable_tabs", "sync_user_info"}:
                    value = int(bool(value))
                elif key == "custom_proxy_port" and value is not None and value != "":
                    value = int(value)
                sets.append(f"{key} = ?")
                params.append(value)
            if not sets:
                return False
            sets.append("update_time = ?")
            params.append(_now())
            params.append(code)
            cur = self._conn.execute(
                f"UPDATE environments SET {', '.join(sets)} WHERE code = ?", params
            )
            self._conn.commit()
            return cur.rowcount > 0

    def set_runtime(self, code: str, pid: Optional[int], debug_port: Optional[int]) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE environments SET pid = ?, debug_port = ? WHERE code = ?",
                (pid, debug_port, code),
            )
            self._conn.commit()

    def delete_environment(self, code: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM environments WHERE code = ?", (code,))
            self._conn.commit()
            return cur.rowcount > 0

    # -- proxies --------------------------------------------------------------
    def insert_proxy(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            code = new_code()
            now = _now()
            record = {
                "code": code,
                "proxy_name": fields["proxy_name"],
                "proxy_type": fields["proxy_type"],
                "proxy_addr": fields["proxy_addr"],
                "proxy_port": int(fields["proxy_port"]),
                "username": fields.get("username", ""),
                "password": fields.get("password", ""),
                "remark": fields.get("remark", ""),
                "create_time": now,
                "update_time": now,
            }
            cols = ", ".join(record.keys())
            ph = ", ".join("?" for _ in record)
            self._conn.execute(
                f"INSERT INTO proxies ({cols}) VALUES ({ph})", list(record.values())
            )
            self._conn.commit()
            return self.get_proxy(code)  # type: ignore[return-value]

    def get_proxy(self, code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM proxies WHERE code = ?", (code,)
            ).fetchone()
            return self._row_to_dict(row)

    def list_proxies(
        self, page: int = 1, page_size: int = 20, keyword: str = ""
    ) -> Tuple[List[Dict[str, Any]], int]:
        with self._lock:
            where, params = "", []
            if keyword:
                where = "WHERE proxy_name LIKE ? OR proxy_addr LIKE ? OR code LIKE ?"
                like = f"%{keyword}%"
                params = [like, like, like]
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM proxies {where}", params
            ).fetchone()[0]
            offset = max(page - 1, 0) * page_size
            rows = self._conn.execute(
                f"SELECT * FROM proxies {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params + [page_size, offset],
            ).fetchall()
            return [self._row_to_dict(r) for r in rows], total  # type: ignore[misc]

    def update_proxy(self, code: str, fields: Dict[str, Any]) -> bool:
        allowed = {
            "proxy_name", "proxy_type", "proxy_addr", "proxy_port",
            "username", "password", "remark",
        }
        with self._lock:
            sets, params = [], []
            for key, value in fields.items():
                if key not in allowed:
                    continue
                if key == "proxy_port":
                    value = int(value)
                sets.append(f"{key} = ?")
                params.append(value)
            if not sets:
                return False
            sets.append("update_time = ?")
            params.append(_now())
            params.append(code)
            cur = self._conn.execute(
                f"UPDATE proxies SET {', '.join(sets)} WHERE code = ?", params
            )
            self._conn.commit()
            return cur.rowcount > 0

    def delete_proxy(self, code: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM proxies WHERE code = ?", (code,))
            self._conn.commit()
            return cur.rowcount > 0

    # -- error reports --------------------------------------------------------
    def insert_error(self, title: str, detail: Optional[str], type_: Optional[str]) -> str:
        with self._lock:
            # short, collision-checked code
            while True:
                code = secrets.token_hex(4)
                exists = self._conn.execute(
                    "SELECT 1 FROM browser_errors WHERE code = ?", (code,)
                ).fetchone()
                if not exists:
                    break
            self._conn.execute(
                "INSERT INTO browser_errors (code, title, detail, type, create_time) "
                "VALUES (?, ?, ?, ?, ?)",
                (code, title, detail or None, type_ or None, _now()),
            )
            self._conn.commit()
            return code

    def get_error(self, code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM browser_errors WHERE code = ?", (code,)
            ).fetchone()
            return dict(row) if row else None

    # -- config key/value -----------------------------------------------------
    def get_config(self, key: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM config WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else None

    def set_config(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
