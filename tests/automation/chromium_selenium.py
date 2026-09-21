"""Attach Selenium to an existing Qiyuan Chromium with a matching ChromeDriver."""

import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from _api import close_browser, open_browser

CODE = "20d6fe50631423e693c9260661b33b39"
URL = "https://example.com"
CHROMEDRIVER_PATH = ""  # Optional local driver matching the browser's major version.

BUILD_INDEX = "https://googlechromelabs.github.io/chrome-for-testing/latest-patch-versions-per-build-with-downloads.json"
MILESTONE_INDEX = "https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json"


def read_json(url):
    with urlopen(url, timeout=60) as response:
        return json.load(response)


def browser_version(endpoint):
    info = read_json(endpoint + "/json/version")
    match = re.search(r"\d+\.\d+\.\d+\.\d+", info.get("Browser", ""))
    if not match:
        raise RuntimeError(f"CDP did not report a Chromium version: {info}")
    return match.group()


def driver_version(path):
    if not path.is_file():
        return None
    result = subprocess.run([str(path), "--version"], capture_output=True, text=True, timeout=10, check=True)
    match = re.search(r"\d+\.\d+\.\d+\.\d+", result.stdout)
    return match.group() if match else None


def matching_driver(version):
    major = version.split(".")[0]
    if CHROMEDRIVER_PATH:
        path = Path(CHROMEDRIVER_PATH)
        installed = driver_version(path)
        if not installed or installed.split(".")[0] != major:
            raise RuntimeError(f"CHROMEDRIVER_PATH has version {installed}, but browser is {version}")
        return path

    cache = Path.home() / ".cache" / "qiyuan-cloud-sdk" / "chromedriver"
    for path in cache.glob(f"{major}.*/*/chromedriver.exe"):
        installed = driver_version(path)
        if installed and installed.split(".")[0] == major:
            return path

    build = ".".join(version.split(".")[:3])
    release = read_json(BUILD_INDEX).get("builds", {}).get(build)
    if not release:
        release = read_json(MILESTONE_INDEX).get("milestones", {}).get(major)
    if not release:
        raise RuntimeError(f"No official ChromeDriver release found for Chromium {version}")
    platform = "win64" if sys.maxsize > 2**32 else "win32"
    download = next((item for item in release.get("downloads", {}).get("chromedriver", [])
                     if item.get("platform") == platform), None)
    if not download:
        raise RuntimeError(f"No ChromeDriver download for {platform}, version {release['version']}")
    path = cache / release["version"] / platform / "chromedriver.exe"
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading ChromeDriver {release['version']} for Chromium {version}")
    with urlopen(download["url"], timeout=120) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    member = next((name for name in archive.namelist() if name.endswith("/chromedriver.exe")), None)
    if not member:
        raise RuntimeError("ChromeDriver archive does not contain chromedriver.exe")
    temporary = path.with_suffix(".download")
    temporary.write_bytes(archive.read(member))
    temporary.replace(path)
    installed = driver_version(path)
    if not installed or installed.split(".")[0] != major:
        raise RuntimeError(f"Downloaded ChromeDriver {installed} does not match Chromium {version}")
    return path


if __name__ == "__main__":
    opened = open_browser(CODE, "chrome")
    driver = None
    try:
        version = browser_version(opened["debug_endpoint"])
        service = Service(executable_path=str(matching_driver(version)))
        options = webdriver.ChromeOptions()
        options.debugger_address = f"127.0.0.1:{opened['debug_port']}"
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(URL)
        print({"kernel": opened["browser_kernel"], "browser_version": version,
               "title": driver.title, "url": driver.current_url})
    finally:
        if driver:
            driver.quit()
        close_browser(CODE)
