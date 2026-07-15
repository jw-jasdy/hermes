#!/usr/bin/env python3
"""Dependency-free Google Contacts CLI for Hermes using the People API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PEOPLE_API = "https://people.googleapis.com/v1"
TOKEN_URI = "https://oauth2.googleapis.com/token"
CONTACT_SCOPE = "https://www.googleapis.com/auth/contacts"
PERSON_FIELDS = (
    "names,emailAddresses,phoneNumbers,organizations,addresses,"
    "birthdays,biographies,urls,metadata"
)


def fail(message: str, *, details: Any | None = None) -> "NoReturn":
    payload: dict[str, Any] = {"error": message}
    if details is not None:
        payload["details"] = details
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
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
TOKEN_PATH = CONFIG_DIR / "google_contacts_token.json"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"Missing Google OAuth token: {path}")
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Could not read Google OAuth token: {exc}")
    if not isinstance(value, dict):
        fail("Google OAuth token must be a JSON object")
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
    if CONTACT_SCOPE not in scopes:
        fail(
            "Stored Contacts token lacks Contacts access; authorize service=contacts",
            details={"required": CONTACT_SCOPE, "granted": sorted(scopes)},
        )


def refresh_token(payload: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    validate_scope(payload)
    expiry = parse_expiry(payload.get("expiry"))
    if (
        not force
        and payload.get("token")
        and expiry
        and expiry > datetime.now(timezone.utc) + timedelta(seconds=60)
    ):
        return payload
    required = ("refresh_token", "client_id", "client_secret")
    missing = [name for name in required if not payload.get(name)]
    if missing:
        fail("Stored Google token cannot be refreshed", details={"missing": missing})
    request = urllib.request.Request(
        str(payload.get("token_uri") or TOKEN_URI),
        data=urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": payload["refresh_token"],
                "client_id": payload["client_id"],
                "client_secret": payload["client_secret"],
            }
        ).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(raw)
        except json.JSONDecodeError:
            details = raw
        fail(f"Google OAuth refresh failed with HTTP {exc.code}", details=details)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"Google OAuth refresh failed: {exc}")
    token = result.get("access_token")
    if not token:
        fail("Google OAuth refresh returned no access_token", details=result)
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


def api_request(
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    retry_auth: bool = True,
) -> Any:
    token_payload = refresh_token(read_json(TOKEN_PATH))
    url = f"{PEOPLE_API}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query, doseq=True)}"
    data = None
    headers = {
        "Authorization": f"Bearer {token_payload['token']}",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401 and retry_auth:
            refresh_token(read_json(TOKEN_PATH), force=True)
            return api_request(
                method,
                path,
                query=query,
                body=body,
                retry_auth=False,
            )
        try:
            details = json.loads(raw)
        except json.JSONDecodeError:
            details = raw
        fail(f"People API request failed with HTTP {exc.code}", details=details)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"People API request failed: {exc}")


def output(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def resource_name(value: str) -> str:
    cleaned = value.strip().strip("/")
    if not cleaned:
        fail("Contact resource name is empty")
    return cleaned if cleaned.startswith("people/") else f"people/{cleaned}"


def person_path(value: str, suffix: str = "") -> str:
    encoded = urllib.parse.quote(resource_name(value), safe="/")
    return f"{encoded}{suffix}"


def first_value(items: list[dict[str, Any]] | None, key: str) -> str:
    for item in items or []:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def normalize_person(person: dict[str, Any]) -> dict[str, Any]:
    names = person.get("names") or []
    primary_name = names[0] if names else {}
    organizations = person.get("organizations") or []
    primary_org = organizations[0] if organizations else {}
    birthdays = person.get("birthdays") or []
    birthday = (birthdays[0].get("date") if birthdays else None) or {}
    return {
        "resourceName": person.get("resourceName"),
        "etag": person.get("etag"),
        "displayName": primary_name.get("displayName") or primary_name.get("unstructuredName") or "",
        "givenName": primary_name.get("givenName") or "",
        "familyName": primary_name.get("familyName") or "",
        "emails": [
            {"value": item.get("value", ""), "type": item.get("type", "")}
            for item in person.get("emailAddresses") or []
        ],
        "phones": [
            {"value": item.get("value", ""), "type": item.get("type", "")}
            for item in person.get("phoneNumbers") or []
        ],
        "company": primary_org.get("name") or "",
        "jobTitle": primary_org.get("title") or "",
        "addresses": [
            {
                "formattedValue": item.get("formattedValue", ""),
                "type": item.get("type", ""),
            }
            for item in person.get("addresses") or []
        ],
        "birthday": (
            f"{int(birthday.get('year')):04d}-{int(birthday.get('month')):02d}-{int(birthday.get('day')):02d}"
            if birthday.get("year") and birthday.get("month") and birthday.get("day")
            else ""
        ),
        "notes": first_value(person.get("biographies"), "value"),
        "urls": [
            {"value": item.get("value", ""), "type": item.get("type", "")}
            for item in person.get("urls") or []
        ],
    }


def list_connections(maximum: int) -> list[dict[str, Any]]:
    maximum = max(1, min(maximum, 5000))
    people: list[dict[str, Any]] = []
    page_token: str | None = None
    while len(people) < maximum:
        query: dict[str, Any] = {
            "personFields": PERSON_FIELDS,
            "pageSize": min(1000, maximum - len(people)),
            "sortOrder": "LAST_MODIFIED_DESCENDING",
        }
        if page_token:
            query["pageToken"] = page_token
        result = api_request("GET", "people/me/connections", query=query)
        people.extend(result.get("connections") or [])
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return people[:maximum]


def contacts_list(args: argparse.Namespace) -> None:
    output([normalize_person(person) for person in list_connections(args.max_results)])


def contacts_search(args: argparse.Namespace) -> None:
    needle = args.query.casefold().strip()
    if not needle:
        fail("Search query must not be empty")
    matches: list[dict[str, Any]] = []
    scan_limit = max(args.max_results, min(args.scan_limit, 5000))
    for person in list_connections(scan_limit):
        normalized = normalize_person(person)
        haystack = json.dumps(normalized, ensure_ascii=False).casefold()
        if needle in haystack:
            matches.append(normalized)
            if len(matches) >= args.max_results:
                break
    output(matches)


def get_person_raw(value: str) -> dict[str, Any]:
    result = api_request(
        "GET",
        person_path(value),
        query={"personFields": PERSON_FIELDS},
    )
    if not isinstance(result, dict):
        fail("People API returned no contact")
    return result


def contacts_get(args: argparse.Namespace) -> None:
    output(normalize_person(get_person_raw(args.resource_name)))


def parse_birthday(value: str) -> dict[str, int]:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        fail("Birthday must use YYYY-MM-DD")
    return {"year": parsed.year, "month": parsed.month, "day": parsed.day}


def build_contact_fields(args: argparse.Namespace, *, for_update: bool) -> tuple[dict[str, Any], list[str]]:
    fields: dict[str, Any] = {}
    changed: list[str] = []

    name_requested = args.given_name is not None or args.family_name is not None
    if name_requested:
        name: dict[str, str] = {}
        if args.given_name:
            name["givenName"] = args.given_name
        if args.family_name:
            name["familyName"] = args.family_name
        fields["names"] = [name] if name else []
        changed.append("names")

    if args.email is not None or getattr(args, "clear_emails", False):
        fields["emailAddresses"] = (
            [] if getattr(args, "clear_emails", False)
            else [{"value": value} for value in args.email or [] if value.strip()]
        )
        changed.append("emailAddresses")

    if args.phone is not None or getattr(args, "clear_phones", False):
        fields["phoneNumbers"] = (
            [] if getattr(args, "clear_phones", False)
            else [{"value": value} for value in args.phone or [] if value.strip()]
        )
        changed.append("phoneNumbers")

    org_requested = args.company is not None or args.job_title is not None
    if org_requested or getattr(args, "clear_organization", False):
        if getattr(args, "clear_organization", False):
            fields["organizations"] = []
        else:
            organization: dict[str, str] = {}
            if args.company:
                organization["name"] = args.company
            if args.job_title:
                organization["title"] = args.job_title
            fields["organizations"] = [organization] if organization else []
        changed.append("organizations")

    if args.notes is not None or getattr(args, "clear_notes", False):
        fields["biographies"] = (
            [] if getattr(args, "clear_notes", False)
            else [{"value": args.notes}] if args.notes else []
        )
        changed.append("biographies")

    if args.birthday is not None or getattr(args, "clear_birthday", False):
        fields["birthdays"] = (
            [] if getattr(args, "clear_birthday", False)
            else [{"date": parse_birthday(args.birthday)}]
        )
        changed.append("birthdays")

    if args.url is not None or getattr(args, "clear_urls", False):
        fields["urls"] = (
            [] if getattr(args, "clear_urls", False)
            else [{"value": value} for value in args.url or [] if value.strip()]
        )
        changed.append("urls")

    if not changed:
        fail("Provide at least one contact field to create or update")
    if not for_update and fields.get("names") == []:
        fields.pop("names", None)
        changed = [field for field in changed if field != "names"]
    if not fields:
        fail("Provide at least one non-empty contact field")
    return fields, changed


def contacts_create(args: argparse.Namespace) -> None:
    fields, _ = build_contact_fields(args, for_update=False)
    result = api_request(
        "POST",
        "people:createContact",
        query={"personFields": PERSON_FIELDS},
        body=fields,
    )
    output(normalize_person(result))


def contacts_update(args: argparse.Namespace) -> None:
    current = get_person_raw(args.resource_name)
    fields, changed = build_contact_fields(args, for_update=True)
    metadata = current.get("metadata")
    if not current.get("resourceName") or not metadata:
        fail("People API contact is missing resourceName or metadata")
    body: dict[str, Any] = {
        "resourceName": current.get("resourceName"),
        "etag": current.get("etag"),
        "metadata": metadata,
    }
    body.update(fields)
    result = api_request(
        "PATCH",
        person_path(args.resource_name, ":updateContact"),
        query={
            "updatePersonFields": ",".join(changed),
            "personFields": PERSON_FIELDS,
        },
        body=body,
    )
    output(normalize_person(result))


def contacts_delete(args: argparse.Namespace) -> None:
    api_request("DELETE", person_path(args.resource_name, ":deleteContact"))
    output({"deleted": True, "resourceName": resource_name(args.resource_name)})


def contacts_check(_: argparse.Namespace) -> None:
    result = api_request(
        "GET",
        "people/me/connections",
        query={"personFields": "names", "pageSize": 1},
    )
    output(
        {
            "authenticated": True,
            "contactsReachable": isinstance(result.get("connections") or [], list),
            "scope": CONTACT_SCOPE,
            "runtime": "python-stdlib",
        }
    )


def add_contact_fields(command: argparse.ArgumentParser, *, update: bool) -> None:
    command.add_argument("--given-name")
    command.add_argument("--family-name")
    command.add_argument("--email", action="append")
    command.add_argument("--phone", action="append")
    command.add_argument("--company")
    command.add_argument("--job-title")
    command.add_argument("--notes")
    command.add_argument("--birthday")
    command.add_argument("--url", action="append")
    if update:
        command.add_argument("--clear-emails", action="store_true")
        command.add_argument("--clear-phones", action="store_true")
        command.add_argument("--clear-organization", action="store_true")
        command.add_argument("--clear-notes", action="store_true")
        command.add_argument("--clear-birthday", action="store_true")
        command.add_argument("--clear-urls", action="store_true")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    commands.add_parser("check").set_defaults(handler=contacts_check)

    list_command = commands.add_parser("list")
    list_command.add_argument("--max", dest="max_results", type=int, default=100)
    list_command.set_defaults(handler=contacts_list)

    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--max", dest="max_results", type=int, default=25)
    search.add_argument("--scan-limit", type=int, default=1000)
    search.set_defaults(handler=contacts_search)

    get_command = commands.add_parser("get")
    get_command.add_argument("resource_name")
    get_command.set_defaults(handler=contacts_get)

    create = commands.add_parser("create")
    add_contact_fields(create, update=False)
    create.set_defaults(handler=contacts_create)

    update = commands.add_parser("update")
    update.add_argument("resource_name")
    add_contact_fields(update, update=True)
    update.set_defaults(handler=contacts_update)

    delete = commands.add_parser("delete")
    delete.add_argument("resource_name")
    delete.set_defaults(handler=contacts_delete)

    return root


def main() -> None:
    args = parser().parse_args()
    handler = getattr(args, "handler", None)
    if handler is None:
        fail("No Contacts command selected")
    handler(args)


if __name__ == "__main__":
    main()
