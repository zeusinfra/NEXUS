from __future__ import annotations

import ipaddress
import os
from urllib.parse import parse_qs

from fastapi import HTTPException, Request

from zeus_core.config_guard import LanSecurityConfig, remote_auth_required


LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def is_local_host(host: str | None) -> bool:
    return bool(host and host in LOCAL_HOSTS)


def is_local_request(request: Request) -> bool:
    client = request.client
    return bool(client and is_local_host(client.host))


def is_trusted_host(
    host: str | None, *, allow_lan: bool, trusted_ips: str | None = None
) -> bool:
    if not host:
        return False
    if is_local_host(host):
        return True

    trusted = {
        item.strip()
        for item in (
            trusted_ips
            if trusted_ips is not None
            else os.getenv("ZEUS_TRUSTED_IPS", "")
        ).split(",")
        if item.strip()
    }
    if host in trusted:
        return True

    try:
        ip = ipaddress.ip_address(host)
    except Exception:
        return False

    if ip.is_loopback:
        return True
    return bool(allow_lan and ip.is_private)


def is_trusted_request(request: Request, *, allow_lan: bool) -> bool:
    client = request.client
    return is_trusted_host(client.host if client else None, allow_lan=allow_lan)


def extract_bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.lower().startswith("bearer "):
        return value.split(" ", 1)[1].strip() or None
    return value


def require_lan_token_for_request(request: Request, *, lan: LanSecurityConfig) -> None:
    if not (
        remote_auth_required(allow_lan=lan.allow_lan, bind_host=lan.bind_host)
        and lan.lan_auth_enabled
    ):
        return

    client = request.client
    host = client.host if client else None
    if is_local_host(host):
        return

    if not lan.lan_token:
        raise HTTPException(
            status_code=500, detail="LAN token not configured on server."
        )

    header_token = extract_bearer_token(request.headers.get("authorization"))
    header_token = header_token or extract_bearer_token(
        request.headers.get("x-zeus-token")
    )
    query_token = extract_bearer_token(request.query_params.get("token"))
    if (header_token or query_token) != lan.lan_token:
        raise HTTPException(
            status_code=401, detail="Invalid or missing ZEUS LAN token."
        )


def host_from_socketio_environ(environ: dict) -> str | None:
    try:
        host = environ.get("REMOTE_ADDR")
    except Exception:
        host = None
    if host:
        return host

    try:
        scope = environ.get("asgi.scope") or {}
        client = scope.get("client")
        return client[0] if isinstance(client, (list, tuple)) and client else None
    except Exception:
        return None


def require_lan_token_for_socketio(
    environ: dict, auth_payload: dict | None, *, lan: LanSecurityConfig
) -> bool:
    if not (
        remote_auth_required(allow_lan=lan.allow_lan, bind_host=lan.bind_host)
        and lan.lan_auth_enabled
    ):
        return True

    host = host_from_socketio_environ(environ)
    if is_local_host(host):
        return True
    if not lan.lan_token:
        return False

    provided = None
    if isinstance(auth_payload, dict):
        provided = extract_bearer_token(auth_payload.get("token"))
    if not provided:
        qs = environ.get("QUERY_STRING") or ""
        try:
            parsed = parse_qs(qs)
            provided = extract_bearer_token((parsed.get("token") or [None])[0])
        except Exception:
            provided = None
    if not provided:
        provided = extract_bearer_token(
            environ.get("HTTP_X_ZEUS_TOKEN")
        ) or extract_bearer_token(environ.get("HTTP_AUTHORIZATION"))
    return provided == lan.lan_token
