"""HTTP clients for BiliTools-Plus.

Packaged Windows apps can inherit proxy-related environment variables from the
host. That makes Bilibili QR/login requests slow or fail differently from dev.
Keep env proxy usage off by default; explicit proxy support can be added via
settings later without changing every API call site.
"""
from __future__ import annotations

import httpx
import requests


def create_client(**kwargs) -> httpx.AsyncClient:
    kwargs.setdefault("trust_env", False)
    return httpx.AsyncClient(**kwargs)


def create_requests_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session
