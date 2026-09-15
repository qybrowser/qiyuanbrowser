"""Local qiyuan client-browser process management.

Launches the qiyuan client chrome in ``--mode=client``: the browser is given
only ``uuid`` + ``token`` and pulls / decrypts its own fingerprint from the
server (``GET /api/v1/browser/md5/{uuid}``). Therefore no ``--user-agent``,
``--proxy-server`` or ``--remote-debugging-port`` are passed here.

Launch template (matches the reference command):

    {browser_app_data_dir}\\client\\{version}\\QyBrowser.exe
      --mode=client --uuid={uuid} --token={token}
      --user-data-dir={browser_app_data_dir}\\user_data\\{uuid}
      --browser_app_data_dir={browser_app_data_dir}
      --enable-logging=stderr --log-level=0 --v=1
      --proxy-bypass-list="localhost;127.0.0.1;<local>"
      --no-first-run --new-window --window-position=0,0 --window-size=1280,720
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

from . import qiyuan_config
from .errors import BrowserError

# Fixed flags appended to every client-mode launch.
_FIXED_ARGS = [
    "--enable-logging=stderr",
    "--log-level=0",
    "--v=1",
    "--proxy-bypass-list=localhost;127.0.0.1;<local>",
    "--no-first-run",
    "--new-window",
    "--window-position=0,0",
    "--window-size=1280,720",
]


def pid_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True,
        )
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class BrowserLauncher:
    def __init__(self, browser_app_data_dir: Optional[str] = None) -> None:
        self._procs: Dict[str, subprocess.Popen] = {}
        self.browser_app_data_dir = qiyuan_config.qiyuan_dir(browser_app_data_dir)

    def set_browser_app_data_dir(self, value: str) -> None:
        self.browser_app_data_dir = qiyuan_config.qiyuan_dir(value)

    def user_data_dir(self, uuid: str) -> str:
        return os.path.join(qiyuan_config.user_data_root(self.browser_app_data_dir), uuid)

    def open(
        self,
        env: Dict[str, object],
        token: str,
        extra_args: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        uuid = str(env["code"])
        version = str(env.get("browser_version") or "")
        if not version:
            raise BrowserError("该环境未配置内核版本")
        if not token:
            raise BrowserError("缺少 token，无法以 client 模式启动")

        if self.is_running(env):
            self.close(env)

        chrome = qiyuan_config.chrome_executable(version, self.browser_app_data_dir)
        if not os.path.exists(chrome):
            raise BrowserError(f"未找到内核可执行文件: {chrome}")

        udd = self.user_data_dir(uuid)
        os.makedirs(udd, exist_ok=True)

        args: List[str] = [
            chrome,
            "--mode=client",
            f"--uuid={uuid}",
            f"--token={token}",
            f"--user-data-dir={udd}",
            f"--browser_app_data_dir={self.browser_app_data_dir}",
            *_FIXED_ARGS,
        ]
        launch_args = str(env.get("launch_args") or "").strip()
        if launch_args:
            args.extend(launch_args.split())
        if extra_args:
            args.extend(extra_args)

        try:
            proc = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except OSError as exc:  # pragma: no cover - depends on local env
            raise BrowserError(f"启动浏览器失败: {exc}") from exc

        self._procs[uuid] = proc
        return {"pid": proc.pid}

    def is_running(self, env: Dict[str, object]) -> bool:
        uuid = str(env["code"])
        proc = self._procs.get(uuid)
        if proc and proc.poll() is None:
            return True
        if proc and proc.poll() is not None:
            self._procs.pop(uuid, None)
        return pid_alive(env.get("pid"))  # type: ignore[arg-type]

    def close(self, env: Dict[str, object]) -> None:
        uuid = str(env["code"])
        proc = self._procs.pop(uuid, None)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            return
        pid = env.get("pid")
        if pid_alive(pid):  # type: ignore[arg-type]
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                try:
                    os.kill(int(pid), 15)  # type: ignore[arg-type]
                except OSError:
                    pass

    def clear_cache(self, uuid: str) -> None:
        udd = self.user_data_dir(uuid)
        if os.path.isdir(udd):
            shutil.rmtree(udd, ignore_errors=True)
