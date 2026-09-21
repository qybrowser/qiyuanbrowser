"""SQLite persistence layer.

Holds environment, proxy, and extension tables. The fingerprint is stored
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
    browser_kernel  TEXT NOT NULL DEFAULT 'chrome',
    user_agent      TEXT,
    proxy_code      TEXT,
    proxy_mode      TEXT NOT NULL DEFAULT 'no_proxy',
    custom_proxy_type     TEXT,
    custom_proxy_addr     TEXT,
    custom_proxy_port     INTEGER,
    custom_proxy_username TEXT,
    custom_proxy_password TEXT,
    proxy_input_type TEXT,
    proxy_api_url    TEXT,
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
    proxy_input_type TEXT NOT NULL DEFAULT 'manual',
    proxy_api_url TEXT,
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

CREATE TABLE IF NOT EXISTS extensions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    browser_kernel TEXT NOT NULL DEFAULT 'chrome',
    extension_type TEXT NOT NULL DEFAULT 'normal',
    provider TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    file_name TEXT NOT NULL DEFAULT '',
    file_path TEXT NOT NULL DEFAULT '',
    oss_key TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    file_size INTEGER NOT NULL DEFAULT 0,
    icon_path TEXT NOT NULL DEFAULT '',
    status INTEGER NOT NULL DEFAULT 1,
    create_time TEXT NOT NULL,
    update_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extension_bindings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    extension_code TEXT NOT NULL,
    environment_code TEXT NOT NULL,
    create_time TEXT NOT NULL,
    UNIQUE(extension_code, environment_code)
);

CREATE TABLE IF NOT EXISTS extension_sync_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    environment_code TEXT NOT NULL,
    extension_code TEXT NOT NULL,
    version TEXT NOT NULL,
    target_path TEXT NOT NULL,
    sha256 TEXT NOT NULL DEFAULT '',
    sync_status TEXT NOT NULL DEFAULT 'success',
    error_message TEXT NOT NULL DEFAULT '',
    synced_at TEXT NOT NULL,
    UNIQUE(environment_code, extension_code)
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
    ("browser_kernel", "TEXT NOT NULL DEFAULT 'chrome'"),
    ("proxy_mode", "TEXT NOT NULL DEFAULT 'no_proxy'"),
    ("custom_proxy_type", "TEXT"),
    ("custom_proxy_addr", "TEXT"),
    ("custom_proxy_port", "INTEGER"),
    ("custom_proxy_username", "TEXT"),
    ("custom_proxy_password", "TEXT"),
    ("proxy_input_type", "TEXT"),
    ("proxy_api_url", "TEXT"),
)

_PROXY_MIGRATIONS = (
    ("proxy_input_type", "TEXT NOT NULL DEFAULT 'manual'"),
    ("proxy_api_url", "TEXT"),
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
        proxy_cols = {
            row[1] for row in self._conn.execute("PRAGMA table_info(proxies)").fetchall()
        }
        for name, decl in _PROXY_MIGRATIONS:
            if name not in proxy_cols:
                self._conn.execute(f"ALTER TABLE proxies ADD COLUMN {name} {decl}")

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
                "browser_kernel": fields.get("browser_kernel") or "chrome",
                "user_agent": fields.get("user_agent"),
                "proxy_code": fields.get("proxy_code"),
                "proxy_mode": fields.get("proxy_mode") or "no_proxy",
                "custom_proxy_type": fields.get("custom_proxy_type"),
                "custom_proxy_addr": fields.get("custom_proxy_addr"),
                "custom_proxy_port": fields.get("custom_proxy_port"),
                "custom_proxy_username": fields.get("custom_proxy_username"),
                "custom_proxy_password": fields.get("custom_proxy_password"),
                "proxy_input_type": fields.get("proxy_input_type"),
                "proxy_api_url": fields.get("proxy_api_url"),
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
            "name", "platform", "browser_version", "browser_kernel", "user_agent", "proxy_code",
            "proxy_mode", "custom_proxy_type", "custom_proxy_addr",
            "custom_proxy_port", "custom_proxy_username", "custom_proxy_password",
            "proxy_input_type", "proxy_api_url",
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
                "proxy_input_type": fields.get("proxy_input_type") or "manual",
                "proxy_api_url": fields.get("proxy_api_url"),
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
            "proxy_input_type", "proxy_api_url",
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

    # -- extensions ----------------------------------------------------------
    def insert_extension(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            code = fields["code"]
            now = _now()
            record = {"code": code, "name": fields["name"], "version": fields["version"],
                      "browser_kernel": fields.get("browser_kernel") or "chrome",
                      "extension_type": fields.get("extension_type") or "normal",
                      "provider": fields.get("provider") or "", "source_url": fields.get("source_url") or "",
                      "description": fields.get("description") or "", "file_name": fields.get("file_name") or "",
                      "file_path": fields.get("file_path") or "", "oss_key": fields.get("oss_key") or "",
                      "sha256": fields.get("sha256") or "", "file_size": int(fields.get("file_size") or 0),
                      "icon_path": fields.get("icon_path") or "", "status": int(fields.get("status", 1)),
                      "create_time": now, "update_time": now}
            cols = ", ".join(record); marks = ", ".join("?" for _ in record)
            self._conn.execute(f"INSERT INTO extensions ({cols}) VALUES ({marks})", list(record.values()))
            self._conn.commit()
            return self.get_extension(code)  # type: ignore[return-value]

    def get_extension(self, code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM extensions WHERE code = ?", (code,)).fetchone()
            return self._row_to_dict(row)

    def list_extensions(self, page: int = 1, page_size: int = 20, keyword: str = "", kernel: str = "", extension_type: str = "") -> Tuple[List[Dict[str, Any]], int]:
        with self._lock:
            conditions, params = [], []
            if keyword:
                conditions.append("(name LIKE ? OR code LIKE ? OR provider LIKE ?)"); like = f"%{keyword}%"; params.extend([like, like, like])
            if kernel: conditions.append("browser_kernel = ?"); params.append(kernel)
            if extension_type: conditions.append("extension_type = ?"); params.append(extension_type)
            where = " WHERE " + " AND ".join(conditions) if conditions else ""
            total = self._conn.execute(f"SELECT COUNT(*) FROM extensions{where}", params).fetchone()[0]
            offset = max(page - 1, 0) * page_size
            rows = self._conn.execute(f"SELECT * FROM extensions{where} ORDER BY id DESC LIMIT ? OFFSET ?", params + [page_size, offset]).fetchall()
            return [self._row_to_dict(r) for r in rows], total  # type: ignore[misc]

    def update_extension(self, code: str, fields: Dict[str, Any]) -> bool:
        allowed = {"name", "version", "browser_kernel", "extension_type", "provider", "source_url", "description", "file_name", "file_path", "oss_key", "sha256", "file_size", "icon_path", "status"}
        with self._lock:
            sets, params = [], []
            for key, value in fields.items():
                if key in allowed:
                    if key in {"file_size", "status"}: value = int(value or 0)
                    sets.append(f"{key} = ?"); params.append(value)
            if not sets: return False
            sets.append("update_time = ?"); params.extend([_now(), code])
            cur = self._conn.execute(f"UPDATE extensions SET {', '.join(sets)} WHERE code = ?", params); self._conn.commit()
            return cur.rowcount > 0

    def delete_extension(self, code: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM extensions WHERE code = ?", (code,))
            self._conn.execute("DELETE FROM extension_bindings WHERE extension_code = ?", (code,))
            self._conn.execute("DELETE FROM extension_sync_state WHERE extension_code = ?", (code,))
            self._conn.commit(); return cur.rowcount > 0

    def set_extension_bindings(self, code: str, environments: List[str]) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM extension_bindings WHERE extension_code = ?", (code,))
            now = _now()
            self._conn.executemany("INSERT INTO extension_bindings(extension_code, environment_code, create_time) VALUES (?, ?, ?)", [(code, item, now) for item in dict.fromkeys(environments) if item])
            self._conn.commit()

    def get_extension_bindings(self, code: str) -> List[str]:
        with self._lock:
            return [row[0] for row in self._conn.execute("SELECT environment_code FROM extension_bindings WHERE extension_code = ? ORDER BY id", (code,)).fetchall()]

    def list_environment_extensions(self, environment_code: str) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute("SELECT e.* FROM extensions e JOIN extension_bindings b ON b.extension_code=e.code WHERE e.status=1 AND (b.environment_code='*' OR b.environment_code=?) ORDER BY e.id", (environment_code,)).fetchall()
            return [self._row_to_dict(r) for r in rows]  # type: ignore[misc]

    def upsert_extension_sync(self, environment_code: str, extension_code: str, fields: Dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute("""INSERT INTO extension_sync_state(environment_code, extension_code, version, target_path, sha256, sync_status, error_message, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(environment_code, extension_code) DO UPDATE SET version=excluded.version,target_path=excluded.target_path,sha256=excluded.sha256,sync_status=excluded.sync_status,error_message=excluded.error_message,synced_at=excluded.synced_at""", (environment_code, extension_code, fields.get("version", ""), fields.get("target_path", ""), fields.get("sha256", ""), fields.get("sync_status", "success"), fields.get("error_message", ""), _now()))
            self._conn.commit()

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
