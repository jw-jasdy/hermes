---
name: google-contacts
description: "Managed Google Contacts access through the People API with a separate read/write OAuth token and a dependency-free runtime client."
version: 1.0.0
platforms: [linux]
required_credential_files:
  - path: google_contacts_token.json
    description: Google Contacts read/write OAuth token
  - path: google_client_secret.json
    description: Google OAuth Desktop client
metadata:
  hermes:
    tags: [Google, Contacts, People, OAuth]
---

# Google Contacts — managed Hermes deployment

Use this skill for personal Google Contacts. The runtime client uses only
Python's standard library and the People API.

## Safety rules

1. Read, list, and search requests may run without confirmation.
2. Obtain explicit user confirmation before creating, updating, clearing, or
   deleting any contact.
3. Search first when a name is ambiguous and ask the user to choose.
4. Use only a `people/...` resource name returned by this client. Never guess
   contact IDs.
5. Do not use a browser, another contacts tool, pip, or `googleapiclient`.
6. If the runtime file is missing, report that **Google Workspace Runtime
   Repair** must be run.
7. If the token is missing, report that **Google Workspace Setup** must be run
   once with `service=contacts`.

## Runtime path

```bash
CAPI="${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-contacts/scripts/google_contacts.py"
test -f "$CAPI" || {
  echo "Google Workspace Runtime Repair is required: $CAPI is missing" >&2
  exit 1
}
```

Run only with `/usr/bin/python3`.

## Health check

```bash
/usr/bin/python3 "$CAPI" check
```

A healthy response contains `"contactsReachable": true` and
`"runtime": "python-stdlib"`.

## Read and search

```bash
/usr/bin/python3 "$CAPI" list --max 100
/usr/bin/python3 "$CAPI" search "Ada" --max 25
/usr/bin/python3 "$CAPI" get people/CONTACT_ID
```

Search checks names, email addresses, phone numbers, companies, job titles,
addresses, notes, birthdays, and URLs.

## Create

Only after explicit confirmation:

```bash
/usr/bin/python3 "$CAPI" create \
  --given-name "Ada" \
  --family-name "Lovelace" \
  --email "ada@example.com" \
  --phone "+65 6123 4567" \
  --company "Example Ltd" \
  --job-title "Engineer"
```

Multiple `--email`, `--phone`, and `--url` flags are allowed.

## Update

Only after explicit confirmation. Updates replace only fields named on the
command and use the latest People API metadata and etag:

```bash
/usr/bin/python3 "$CAPI" update people/CONTACT_ID \
  --email "new@example.com" \
  --phone "+65 6987 6543"
```

Clear selected fields explicitly:

```bash
/usr/bin/python3 "$CAPI" update people/CONTACT_ID --clear-phones
/usr/bin/python3 "$CAPI" update people/CONTACT_ID --clear-notes
```

Supported writable fields are names, email addresses, phone numbers, company,
job title, notes, birthday, and URLs.

## Delete

Only after explicit confirmation:

```bash
/usr/bin/python3 "$CAPI" delete people/CONTACT_ID
```

## Operator workflows

- **Google Workspace Setup** with `service=contacts` manages authorization.
- **Google Workspace Runtime Repair** installs and verifies the runtime after
  deployments.
- Contacts uses a separate token from Gmail/Calendar and Drive.
- The temporary callback secret is `GOOGLE_OAUTH_CALLBACK_URL`.
