#!/usr/bin/env python3
"""Dependency-free OAuth helper for Hermes Google Contacts access."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCOPE = "https://www.googleapis.com/auth/contacts"
REDIRECT_URI = "http://127.0.0.1:1"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
REVOKE_URI = "https://oauth2.googleapis.com/revoke"
PEOPLE_API = "https://people.googleapis.com/v1"


def fail(message: str, *, details: Any | None = None) -> "NoReturn":
    if details is None:
        print(f"ERROR: {message}", file=sys.stderr)
    else:
        print(
            f"ERROR: {message}: {json.dumps(details, ensure_ascii=False)}",
            file=sys.stderr,
        )
    raise SystemExit(1)


def config_dir() -> Path:
    explicit = os.environ.get("HERMES_CONFIG_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        candidate = Path(hermes_home).expanduser().resolve()
        return candidate if candidate.name == ".hermes" else candidate / ".hermes"
    return Path.home() / ".hermes"


CONFIG_DIR = config_dir()
CLIENT_PATH = CONFIG_DIR / "google_client_secret.json"
TOKEN_PATH = CONFIG_DIR / "google_contacts_token.json"
PENDING_PATH = CONFIG_DIR / "google_contacts_oauth_pending.json"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing file: {path}")
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"could not read {path}: {exc}")
    if not isinstance(value, dict):
        fail(f"expected a JSON object in {path}")
    return value


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
        path.chmod(0o600)
    finally:
        temporary_path.unlink(missing_ok=True)


def client() -> dict[str, str]:
    payload = read_json(CLIENT_PATH)
    installed = payload.get("installed")
    if not isinstance(installed, dict):
        fail("OAuth credentials must be a Google Desktop app client")
    client_id = installed.get("client_id")
    client_secret = installed.get("client_secret")
    if not client_id or not client_secret:
        fail("OAuth Desktop client is missing client_id or client_secret")
    return {
        "client_id": str(client_id),
        "client_secret": str(client_secret),
        "auth_uri": str(installed.get("auth_uri") or AUTH_URI),
        "token_uri": str(installed.get("token_uri") or TOKEN_URI),
    }


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def auth_url() -> None:
    cfg = client()
    verifier = b64url(secrets.token_bytes(48))
    challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = b64url(secrets.token_bytes(24))
    write_private_json(
        PENDING_PATH,
        {
            "state": state,
            "code_verifier": verifier,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    query = urllib.parse.urlencode(
        {
            "client_id": cfg["client_id"],
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    print(f"{cfg['auth_uri']}?{query}")


def parse_callback(value: str) -> tuple[str, str | None, list[str] | None]:
    value = value.strip()
    if not value:
        fail("empty OAuth callback")
    if not value.startswith(("http://", "https://")):
        return value, None, None
    parsed = urllib.parse.urlparse(value)
    params = urllib.parse.parse_qs(parsed.query)
    error = (params.get("error") or [None])[0]
    if error:
        fail(f"Google returned OAuth error: {error}")
    code = (params.get("code") or [None])[0]
    if not code:
        fail("OAuth callback URL has no code parameter")
    state = (params.get("state") or [None])[0]
    scopes = ((params.get("scope") or [""])[0]).split() or None
    return code, state, scopes


def post_form(url: str, values: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(values).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(raw)
        except json.JSONDecodeError:
            details = raw
        fail(f"OAuth request failed with HTTP {exc.code}", details=details)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"OAuth request failed: {exc}")


def exchange_callback(callback: str) -> None:
    cfg = client()
    pending = read_json(PENDING_PATH)
    code, returned_state, returned_scopes = parse_callback(callback)
    if returned_state and returned_state != pending.get("state"):
        fail("OAuth state mismatch; generate a new authorization URL")
    verifier = str(pending.get("code_verifier") or "")
    if not verifier:
        fail("pending OAuth session has no PKCE verifier")
    result = post_form(
        cfg["token_uri"],
        {
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": str(pending.get("redirect_uri") or REDIRECT_URI),
        },
    )
    access_token = result.get("access_token")
    refresh_token = result.get("refresh_token")
    if not access_token or not refresh_token:
        fail(
            "Contacts OAuth exchange did not return access and refresh tokens",
            details=result,
        )
    actual_scopes = str(
        result.get("scope") or " ".join(returned_scopes or [SCOPE])
    ).split()
    if SCOPE not in actual_scopes:
        fail(
            "Google did not grant Contacts read/write access",
            details={"scopes": actual_scopes},
        )
    payload = {
        "type": "authorized_user",
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "refresh_token": refresh_token,
        "token": access_token,
        "token_uri": cfg["token_uri"],
        "scopes": actual_scopes,
        "expiry": (
            datetime.now(timezone.utc)
            + timedelta(seconds=int(result.get("expires_in") or 3600))
        ).isoformat(),
    }
    write_private_json(TOKEN_PATH, payload)
    PENDING_PATH.unlink(missing_ok=True)
    print("CONTACTS_AUTHENTICATED")


def parse_expiry(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_scope(payload: dict[str, Any]) -> None:
    scopes = set(payload.get("scopes") or [])
    if SCOPE not in scopes:
        fail(
            "stored Contacts token is missing the contacts scope",
            details={"required": SCOPE, "granted": sorted(scopes)},
        )


def refresh(payload: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    validate_scope(payload)
    expiry = parse_expiry(payload.get("expiry"))
    if (
        not force
        and payload.get("token")
        and expiry
        and expiry > datetime.now(timezone.utc) + timedelta(seconds=60)
    ):
        return payload
    result = post_form(
        str(payload.get("token_uri") or TOKEN_URI),
        {
            "client_id": str(payload.get("client_id") or ""),
            "client_secret": str(payload.get("client_secret") or ""),
            "refresh_token": str(payload.get("refresh_token") or ""),
            "grant_type": "refresh_token",
        },
    )
    token = result.get("access_token")
    if not token:
        fail("Contacts token refresh returned no access_token", details=result)
    payload["token"] = token
    payload["expiry"] = (
        datetime.now(timezone.utc)
        + timedelta(seconds=int(result.get("expires_in") or 3600))
    ).isoformat()
    if result.get("scope"):
        payload["scopes"] = str(result["scope"]).split()
        validate_scope(payload)
    write_private_json(TOKEN_PATH, payload)
    return payload


def check() -> None:
    payload = refresh(read_json(TOKEN_PATH))
    request = urllib.request.Request(
        f"{PEOPLE_API}/people/me/connections?personFields=names&pageSize=1",
        headers={
            "Authorization": f"Bearer {payload['token']}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        fail(f"Contacts live check failed with HTTP {exc.code}", details=raw)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Contacts live check failed: {exc}")
    print(
        json.dumps(
            {
                "authenticated": True,
                "contactsReachable": isinstance(result.get("connections") or [], list),
                "scope": SCOPE,
                "runtime": "python-stdlib",
            },
            ensure_ascii=False,
        )
    )


def disconnect() -> None:
    TOKEN_PATH.unlink(missing_ok=True)
    PENDING_PATH.unlink(missing_ok=True)
    print("CONTACTS_DISCONNECTED_LOCALLY")


def revoke() -> None:
    if not TOKEN_PATH.exists():
        disconnect()
        return
    payload = read_json(TOKEN_PATH)
    token = payload.get("refresh_token") or payload.get("token")
    if token:
        try:
            post_form(REVOKE_URI, {"token": str(token)})
        except SystemExit:
            print("WARNING: remote revocation failed", file=sys.stderr)
    disconnect()
    print(
        "WARNING: Google revocation may affect other tokens issued to the same OAuth client.",
        file=sys.stderr,
    )


def paths() -> None:
    print(
        json.dumps(
            {
                "client": str(CLIENT_PATH),
                "token": str(TOKEN_PATH),
                "pending": str(PENDING_PATH),
                "scope": SCOPE,
                "redirect_uri": REDIRECT_URI,
                "runtime": "python-stdlib",
            },
            indent=2,
        )
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("auth-url")
    auth_code = commands.add_parser("auth-code")
    auth_code.add_argument("callback")
    commands.add_parser("auth-code-stdin")
    commands.add_parser("check")
    commands.add_parser("disconnect")
    commands.add_parser("revoke")
    commands.add_parser("paths")
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "auth-url":
        auth_url()
    elif args.command == "auth-code":
        exchange_callback(args.callback)
    elif args.command == "auth-code-stdin":
        exchange_callback(sys.stdin.read())
    elif args.command == "check":
        check()
    elif args.command == "disconnect":
        disconnect()
    elif args.command == "revoke":
        revoke()
    elif args.command == "paths":
        paths()


if __name__ == "__main__":
    main()
