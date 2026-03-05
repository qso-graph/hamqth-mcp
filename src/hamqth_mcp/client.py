"""HamQTH API client — XML session auth + JSON DXCC endpoint."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from . import __version__

_BASE = "https://www.hamqth.com"
_NS = "https://www.hamqth.com"  # XML namespace

# Session TTL: re-auth after 55 min (5-min safety margin on 1-hour expiry)
_SESSION_TTL = 55 * 60

# Cache TTLs
_LOOKUP_TTL = 300.0  # 5 minutes
_DXCC_TTL = 3600.0  # 1 hour
_DX_SPOTS_TTL = 15.0  # 15 seconds (spots update every 15s)
_RBN_TTL = 15.0  # 15 seconds
_VERIFY_TTL = 300.0  # 5 minutes


def _is_mock() -> bool:
    return os.getenv("HAMQTH_MCP_MOCK") == "1"


# Mock XML for testing
_MOCK_LOOKUP_XML = """<?xml version="1.0"?>
<HamQTH xmlns="https://www.hamqth.com" version="2.7">
  <search>
    <callsign>OK2CQR</callsign>
    <nick>Petr</nick>
    <qth>Halenkov</qth>
    <country>Czech Republic</country>
    <adif>503</adif>
    <grid>JN89dm</grid>
    <adr_name>Petr Hlozek</adr_name>
    <latitude>49.326</latitude>
    <longitude>18.152</longitude>
    <continent>EU</continent>
    <cq>15</cq>
    <itu>28</itu>
    <lotw>Y</lotw>
    <eqsl>Y</eqsl>
    <qsl>Y</qsl>
    <qsldirect>Y</qsldirect>
    <email>ok2cqr@example.com</email>
    <web>https://www.ok2cqr.com</web>
    <picture>https://www.hamqth.com/userfiles/o/ok/ok2cqr/_profile/ok2cqr_0.jpg</picture>
  </search>
  <session>
    <session_id>mock-session-id</session_id>
  </session>
</HamQTH>"""

_MOCK_BIO_XML = """<?xml version="1.0"?>
<HamQTH xmlns="https://www.hamqth.com" version="2.7">
  <bio>
    <callsign>OK2CQR</callsign>
    <bio>Petr is the creator and maintainer of HamQTH.com and CQRLog.</bio>
  </bio>
</HamQTH>"""

_MOCK_ACTIVITY_XML = """<?xml version="1.0"?>
<HamQTH xmlns="https://www.hamqth.com" version="2.7">
  <search>
    <callsign>KI7MT</callsign>
    <activity>
      <item>
        <type>dx_cluster</type>
        <spotter>W1AW</spotter>
        <freq>14074.0</freq>
        <band>20m</band>
        <mode>FT8</mode>
        <datetime>2026-03-04 12:00:00</datetime>
      </item>
    </activity>
  </search>
</HamQTH>"""

_MOCK_DXCC_JSON = {
    "callsign": "VP8PJ",
    "name": "South Shetland Islands",
    "continent": "SA",
    "utc": "+3",
    "waz": 13,
    "itu": 73,
    "lat": -62.08,
    "lon": -58.67,
    "adif": 241,
}

_MOCK_DX_CSV = (
    "JA1XYZ^14074.0^2026-03-05 12:00:00^W1AW^FT8 -12dB^Y^N^AS^20m^Japan^339\n"
    "VP8PJ^7074.0^2026-03-05 11:55:00^KI7MT^FT8 -08dB^N^N^SA^40m^South Shetland Islands^241\n"
    "OK2CQR^21074.0^2026-03-05 11:50:00^DL1ABC^FT8 -15dB^Y^Y^EU^15m^Czech Republic^503\n"
)

_MOCK_RBN_JSON = {
    "DL1ABC": {
        "dxcall": "DL1ABC",
        "freq": "14023.4",
        "mode": "CW",
        "age": 4,
        "lsn": {"W3LPL": 22, "K1TTT": 18},
    },
    "OK2CQR": {
        "dxcall": "OK2CQR",
        "freq": "7012.0",
        "mode": "CW",
        "age": 12,
        "lsn": {"W1AW": 15},
    },
}

_MOCK_VERIFY_XML = """<?xml version="1.0"?>
<savp>
  <result>Y</result>
  <mycall>KI7MT</mycall>
  <hiscall>OK2CQR</hiscall>
  <date>20260305</date>
  <band>20M</band>
  <message>QSO verified</message>
</savp>"""


class HamQTHClient:
    """HamQTH API client with lazy session management."""

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._session_time: float = 0.0
        self._username: str | None = None
        self._password: str | None = None
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, Any]] = {}

    def configure(self, username: str, password: str) -> None:
        with self._lock:
            self._username = username
            self._password = password

    def _cache_get(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires, value = entry
        if time.monotonic() > expires:
            del self._cache[key]
            return None
        return value

    def _cache_set(self, key: str, value: Any, ttl: float) -> None:
        self._cache[key] = (time.monotonic() + ttl, value)

    def _get_xml(self, url: str) -> ET.Element:
        """HTTP GET, return parsed XML root.

        Catches all urllib exceptions to prevent credential-bearing URLs
        from leaking through error messages (login puts password in query params).
        """
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"hamqth-mcp/{__version__}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except Exception:
            raise RuntimeError("HamQTH request failed — check network and credentials")
        return ET.fromstring(body)

    def _get_json(self, url: str) -> Any:
        """HTTP GET, return parsed JSON."""
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"hamqth-mcp/{__version__}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except Exception:
            raise RuntimeError("HamQTH request failed — check network connectivity")
        return json.loads(body)

    def _get_text(self, url: str) -> str:
        """HTTP GET, return raw text body."""
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"hamqth-mcp/{__version__}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            raise RuntimeError("HamQTH request failed — check network connectivity")

    def _login(self) -> str:
        """Authenticate and return session ID."""
        if not self._username or not self._password:
            raise ValueError("HamQTH credentials not configured")

        params = urllib.parse.urlencode({
            "u": self._username,
            "p": self._password,
            "prg": "adif-mcp",
        })
        root = self._get_xml(f"{_BASE}/xml.php?{params}")

        # Check for error
        err = root.find(f".//{{{_NS}}}error")
        if err is not None and err.text:
            raise RuntimeError(f"HamQTH login failed: {err.text}")

        sid = root.find(f".//{{{_NS}}}session_id")
        if sid is None or not sid.text:
            raise RuntimeError("HamQTH: no session_id in login response")

        with self._lock:
            self._session_id = sid.text
            self._session_time = time.monotonic()
        return sid.text

    def _ensure_session(self) -> str:
        """Return a valid session ID, logging in if needed."""
        with self._lock:
            if self._session_id and (time.monotonic() - self._session_time) < _SESSION_TTL:
                return self._session_id
        return self._login()

    def _xml_request(self, endpoint: str, params: dict[str, str], retry: bool = True) -> ET.Element:
        """Make an authenticated XML request. Re-login on session expiry."""
        sid = self._ensure_session()
        params["id"] = sid
        params["prg"] = "adif-mcp"
        qs = urllib.parse.urlencode(params)
        root = self._get_xml(f"{_BASE}/{endpoint}?{qs}")

        # Check for session expiry
        err = root.find(f".//{{{_NS}}}error")
        if err is not None and err.text and "session" in err.text.lower():
            if retry:
                with self._lock:
                    self._session_id = None
                return self._xml_request(endpoint, params, retry=False)
            raise RuntimeError(f"HamQTH error: {err.text}")

        if err is not None and err.text:
            raise RuntimeError(f"HamQTH error: {err.text}")

        return root

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def lookup(self, callsign: str) -> dict[str, Any]:
        """Look up a callsign."""
        key = f"lookup:{callsign.upper()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            root = ET.fromstring(_MOCK_LOOKUP_XML)
        else:
            root = self._xml_request("xml.php", {"callsign": callsign.upper()})

        search = root.find(f".//{{{_NS}}}search")
        if search is None:
            return {"callsign": callsign.upper(), "error": "Not found"}

        def _text(tag: str) -> str:
            el = search.find(f"{{{_NS}}}{tag}")
            return (el.text or "").strip() if el is not None else ""

        def _float(tag: str) -> float | None:
            v = _text(tag)
            return float(v) if v else None

        def _int(tag: str) -> int | None:
            v = _text(tag)
            return int(v) if v else None

        rec: dict[str, Any] = {
            "callsign": _text("callsign"),
            "name": _text("adr_name"),
            "nick": _text("nick"),
            "qth": _text("qth"),
            "country": _text("country"),
            "grid": _text("grid"),
            "continent": _text("continent"),
            "email": _text("email"),
            "web": _text("web"),
            "picture": _text("picture"),
            "lotw": _text("lotw"),
            "eqsl": _text("eqsl"),
            "qsl_bureau": _text("qsl"),
            "qsl_direct": _text("qsldirect"),
        }

        dxcc = _int("adif")
        if dxcc is not None:
            rec["dxcc"] = dxcc
        lat = _float("latitude")
        if lat is not None:
            rec["lat"] = lat
        lon = _float("longitude")
        if lon is not None:
            rec["lon"] = lon
        cq = _int("cq")
        if cq is not None:
            rec["cqzone"] = cq
        itu = _int("itu")
        if itu is not None:
            rec["ituzone"] = itu
        iota = _text("iota")
        if iota:
            rec["iota"] = iota

        # Remove empty strings
        rec = {k: v for k, v in rec.items() if v != "" and v is not None}
        self._cache_set(key, rec, _LOOKUP_TTL)
        return rec

    def dxcc(self, query: str) -> dict[str, Any]:
        """Resolve DXCC entity (public, no auth required)."""
        key = f"dxcc:{query.upper()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = _MOCK_DXCC_JSON
        else:
            params = urllib.parse.urlencode({"callsign": query.upper()})
            data = self._get_json(f"{_BASE}/dxcc_json.php?{params}")

        if not data or "error" in data:
            return {"query": query.upper(), "error": data.get("error", "Not found") if data else "Not found"}

        rec = {
            "callsign": data.get("callsign", query.upper()),
            "name": data.get("name", ""),
            "continent": data.get("continent", ""),
            "utc_offset": data.get("utc", ""),
            "cqzone": data.get("waz", 0),
            "ituzone": data.get("itu", 0),
            "dxcc": data.get("adif", 0),
        }
        if "lat" in data:
            rec["lat"] = float(data["lat"])
        if "lon" in data:
            rec["lon"] = float(data["lon"])

        self._cache_set(key, rec, _DXCC_TTL)
        return rec

    def bio(self, callsign: str) -> dict[str, Any]:
        """Fetch operator biography."""
        if _is_mock():
            root = ET.fromstring(_MOCK_BIO_XML)
        else:
            root = self._xml_request("xml_bio.php", {
                "callsign": callsign.upper(),
                "strip_html": "1",
            })

        bio_el = root.find(f".//{{{_NS}}}bio")
        if bio_el is None:
            return {"callsign": callsign.upper(), "bio": None}

        call_el = bio_el.find(f"{{{_NS}}}callsign")
        text_el = bio_el.find(f"{{{_NS}}}bio")
        return {
            "callsign": (call_el.text or callsign).strip().upper() if call_el is not None else callsign.upper(),
            "bio": (text_el.text or "").strip() if text_el is not None else None,
        }

    def activity(self, callsign: str) -> dict[str, Any]:
        """Recent DX cluster, RBN, and logbook activity."""
        if _is_mock():
            root = ET.fromstring(_MOCK_ACTIVITY_XML)
        else:
            root = self._xml_request("xml_recactivity.php", {
                "callsign": callsign.upper(),
            })

        # Parse activity items
        items: list[dict[str, str]] = []
        for item in root.iter(f"{{{_NS}}}item"):
            entry: dict[str, str] = {}
            for child in item:
                tag = child.tag.replace(f"{{{_NS}}}", "")
                if child.text:
                    entry[tag] = child.text.strip()
            if entry:
                items.append(entry)

        return {
            "callsign": callsign.upper(),
            "total": len(items),
            "activity": items,
        }

    def dx_spots(self, limit: int = 60, band: str | None = None) -> list[dict[str, str]]:
        """Live DX cluster spots (public, no auth required)."""
        key = f"dx_spots:{limit}:{band}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            text = _MOCK_DX_CSV
        else:
            params: dict[str, str] = {"limit": str(min(limit, 200))}
            if band:
                params["band"] = band.upper()
            qs = urllib.parse.urlencode(params)
            text = self._get_text(f"{_BASE}/dxc_csv.php?{qs}")

        _FIELDS = (
            "call", "freq", "datetime", "spotter", "comment",
            "lotw", "eqsl", "continent", "band", "country", "dxcc",
        )
        spots: list[dict[str, str]] = []
        for line in text.strip().splitlines():
            parts = line.split("^")
            if len(parts) >= len(_FIELDS):
                spots.append(dict(zip(_FIELDS, parts[:len(_FIELDS)])))
        self._cache_set(key, spots, _DX_SPOTS_TTL)
        return spots

    def rbn(
        self,
        band: str | None = None,
        mode: str | None = None,
        cont: str | None = None,
        fromcont: str | None = None,
        age: int | None = None,
    ) -> list[dict[str, Any]]:
        """Reverse Beacon Network data (public, no auth required)."""
        key = f"rbn:{band}:{mode}:{cont}:{fromcont}:{age}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = _MOCK_RBN_JSON
        else:
            params: dict[str, str] = {"data": "1"}
            if band:
                params["band"] = band
            if mode:
                params["mode"] = mode.upper()
            if cont:
                params["cont"] = cont.upper()
            if fromcont:
                params["fromcont"] = fromcont.upper()
            if age is not None:
                params["age"] = str(age)
            qs = urllib.parse.urlencode(params)
            data = self._get_json(f"{_BASE}/rbn_data.php?{qs}")

        results: list[dict[str, Any]] = []
        if isinstance(data, dict):
            for call, info in data.items():
                if not isinstance(info, dict):
                    continue
                rec: dict[str, Any] = {
                    "call": info.get("dxcall", call),
                    "freq": info.get("freq", ""),
                    "mode": info.get("mode", ""),
                    "age": info.get("age", 0),
                }
                lsn = info.get("lsn")
                if isinstance(lsn, dict):
                    rec["listeners"] = lsn
                results.append(rec)

        self._cache_set(key, results, _RBN_TTL)
        return results

    def verify_qso(
        self, mycall: str, hiscall: str, date: str, band: str
    ) -> dict[str, str]:
        """Verify a QSO via SAVP protocol (public, no auth required)."""
        key = f"verify:{mycall.upper()}:{hiscall.upper()}:{date}:{band.upper()}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            text = _MOCK_VERIFY_XML
        else:
            params = urllib.parse.urlencode({
                "mycall": mycall.upper(),
                "hiscall": hiscall.upper(),
                "date": date,
                "band": band.upper(),
            })
            text = self._get_text(f"{_BASE}/verifyqso.php?{params}")

        root = ET.fromstring(text)
        rec: dict[str, str] = {}
        for child in root:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child.text:
                rec[tag] = child.text.strip()

        self._cache_set(key, rec, _VERIFY_TTL)
        return rec
