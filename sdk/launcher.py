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
import socket
import subprocess
import sys
import time
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
        headless: bool = False,
        open_tabs: bool = False,
        need_debug_port: bool = True,
    ) -> Dict[str, object]:
        uuid = str(env["code"])
        version = str(env.get("browser_version") or "")
        if not version:
            raise BrowserError("该环境未配置内核版本")
        if not token:
            raise BrowserError("缺少 token，无法以 client 模式启动")

        if self.is_running(env):
            self.close(env)

        kernel = "firefox" if env.get("browser_kernel") == "firefox" else "chrome"
        executable = qiyuan_config.browser_executable(version, kernel, self.browser_app_data_dir)
        if not os.path.exists(executable):
            raise BrowserError(f"未找到内核可执行文件: {executable}")

        udd = self.user_data_dir(uuid)
        os.makedirs(udd, exist_ok=True)

        debug_port = _allocate_port() if need_debug_port else None
        common = [executable, "--mode=client", f"--uuid={uuid}", f"--token={token}"]
        if kernel == "firefox":
            args = [*common, f"--browser_app_data_dir={self.browser_app_data_dir}",
                    f"--profile={udd}", "--new-instance", "--wait-for-browser"]
            if headless:
                args.append("--headless")
        else:
            args = [*common, f"--user-data-dir={udd}",
                    f"--browser_app_data_dir={self.browser_app_data_dir}", *_FIXED_ARGS]
            if headless:
                args.append("--headless=new")
            if not open_tabs and not env.get("open_home_page"):
                args.append("--no-tabs=yes")
        if debug_port is not None:
            args.append(f"--remote-debugging-port={debug_port}")
        launch_args = str(env.get("launch_args") or "").strip()
        if launch_args:
            args.extend(launch_args.split())
        if extra_args:
            args.extend(extra_args)

        try:
            process_env = os.environ.copy()
            if kernel == "firefox":
                process_env["MOZ_CRASHREPORTER_DISABLE"] = "1"
            log_dir = os.path.join(self.browser_app_data_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            launch_log = open(os.path.join(log_dir, f"browser-{uuid}.log"), "ab")
            try:
                proc = subprocess.Popen(
                    args, stdout=launch_log, stderr=subprocess.STDOUT, env=process_env
                )
            finally:
                launch_log.close()
        except OSError as exc:  # pragma: no cover - depends on local env
            raise BrowserError(f"启动浏览器失败: {exc}") from exc

        self._procs[uuid] = proc
        if debug_port is not None and not _wait_for_debug_port(debug_port, proc, 30.0, kernel):
            self.close({**env, "pid": proc.pid})
            protocol = "WebDriver BiDi" if kernel == "firefox" else "CDP"
            raise BrowserError(f"{protocol} 端口 {debug_port} 未就绪")
        return {
            "pid": proc.pid,
            "debug_port": debug_port,
            "browser_kernel": kernel,
            "debug_protocol": None if debug_port is None else ("webdriver-bidi" if kernel == "firefox" else "cdp"),
            "debug_endpoint": None if debug_port is None else (
                f"ws://127.0.0.1:{debug_port}/session" if kernel == "firefox"
                else f"http://127.0.0.1:{debug_port}"
            ),
        }

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
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
                return
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            return
        pid = env.get("pid")
        if pid_alive(pid):  # type: ignore[arg-type]
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
            else:
                try:
                    os.kill(int(pid), 15)  # type: ignore[arg-type]
                except OSError:
                    pass

    def clear_cache(self, uuid: str) -> None:
        udd = self.user_data_dir(uuid)
        if os.path.isdir(udd):
            shutil.rmtree(udd, ignore_errors=True)


def _allocate_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    except OSError as exc:
        raise BrowserError(f"无法分配调试端口: {exc}") from exc


def _wait_for_debug_port(port: int, proc: subprocess.Popen, timeout: float, kernel: str) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5) as sock:
                if kernel != "firefox":
                    return True
                request = (
                    f"GET /session HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: Upgrade\r\n"
                    "Upgrade: websocket\r\nSec-WebSocket-Version: 13\r\n"
                    "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n"
                )
                sock.sendall(request.encode("ascii"))
                return sock.recv(256).startswith(b"HTTP/1.1 101")
        except OSError:
            time.sleep(0.15)
    return False
