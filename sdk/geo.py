"""IP geolocation and proxy detection.

Returns the unified structure the client browser expects (compatible with the
Electron ``/api/ip-geo`` / ``/api/check-proxy`` responses):

    { success, ip, country, country_code, region, city,
      latitude, longitude, timezone: { id, abbr, utc }, ... }

Primary source is ipwho.is (already nested); ip-api.com is the fallback.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx

_TIMEOUT = 8.0


def _normalize_ipwhois(geo: Dict[str, Any], latency_ms: int) -> Dict[str, Any]:
    tz = geo.get("timezone") or {}
    conn = geo.get("connection") or {}
    return {
        "success": True, "latency_ms": latency_ms,
        "ip": geo.get("ip", ""), "type": geo.get("type", ""),
        "continent": geo.get("continent", ""), "continent_code": geo.get("continent_code", ""),
        "country": geo.get("country", ""), "country_code": geo.get("country_code", ""),
        "region": geo.get("region", ""), "region_code": geo.get("region_code", ""),
        "city": geo.get("city", ""),
        "latitude": geo.get("latitude"), "longitude": geo.get("longitude"),
        "postal": geo.get("postal", ""), "calling_code": geo.get("calling_code", ""),
        "flag": {"img": (geo.get("flag") or {}).get("img", "")},
        "connection": {"asn": conn.get("asn"), "org": conn.get("org", ""), "isp": conn.get("isp", "")},
        "timezone": {"id": tz.get("id", ""), "abbr": tz.get("abbr", ""), "utc": tz.get("utc", "")},
    }


def _normalize_ipapi(g: Dict[str, Any], latency_ms: int) -> Dict[str, Any]:
    return {
        "success": True, "latency_ms": latency_ms,
        "ip": g.get("query", ""), "type": "",
        "continent": g.get("continent", ""), "continent_code": g.get("continentCode", ""),
        "country": g.get("country", ""), "country_code": g.get("countryCode", ""),
        "region": g.get("regionName", ""), "region_code": g.get("region", ""),
        "city": g.get("city", ""),
        "latitude": g.get("lat"), "longitude": g.get("lon"),
        "postal": g.get("zip", ""), "calling_code": "",
        "flag": {"img": ""},
        "connection": {"asn": None, "org": g.get("org", ""), "isp": g.get("isp", "")},
        "timezone": {"id": g.get("timezone", ""), "abbr": "", "utc": ""},
    }


_IPAPI_FIELDS = (
    "status,message,continent,continentCode,country,countryCode,region,"
    "regionName,city,zip,lat,lon,timezone,offset,isp,org,as,query"
)


def lookup_ip_geo(ip: str = "", proxy: Optional[str] = None) -> Dict[str, Any]:
    """Look up geo for ``ip`` (empty = caller's own IP), optionally via ``proxy``."""
    start = time.time()
    client_kwargs: Dict[str, Any] = {"timeout": _TIMEOUT}
    if proxy:
        # httpx>=0.26 uses `proxy=`; `proxies=` was removed in 0.28
        client_kwargs["proxy"] = proxy
    try:
        with httpx.Client(**client_kwargs) as client:
            # ipwho.is
            try:
                resp = client.get(f"https://ipwho.is/{ip}")
                data = resp.json()
                if data.get("success"):
                    return _normalize_ipwhois(data, int((time.time() - start) * 1000))
            except Exception:
                pass
            # ip-api.com fallback
            resp = client.get(f"http://ip-api.com/json/{ip}?fields={_IPAPI_FIELDS}")
            data = resp.json()
            if data.get("status") == "success":
                return _normalize_ipapi(data, int((time.time() - start) * 1000))
            return {"success": False, "error": data.get("message", "geo lookup failed")}
    except Exception as exc:  # network / proxy failure
        return {"success": False, "error": str(exc)}


def build_proxy_url(proxy_type: str, proxy_addr: str, proxy_port: Any,
                    username: str = "", password: str = "") -> str:
    scheme = (proxy_type or "http").lower()
    auth = f"{username}:{password}@" if username else ""
    return f"{scheme}://{auth}{proxy_addr}:{proxy_port}"


def check_proxy(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a proxy by resolving geo through it. Response mirrors ip-geo."""
    addr = data.get("proxy_addr")
    port = data.get("proxy_port")
    if not addr or not port:
        return {"success": False, "error": "缺少必要参数: proxy_addr, proxy_port"}
    proxy = build_proxy_url(
        data.get("proxy_type", "http"), addr, port,
        data.get("username", ""), data.get("password", ""),
    )
    return lookup_ip_geo("", proxy=proxy)
