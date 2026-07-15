---
name: google-workspace
description: "Managed personal Google services for Gmail, Calendar, Contacts, and a folder-bound Drive/Docs/Sheets workspace. Use this skill for every configured Google service request."
version: 1.3.0
platforms: [linux]
required_credential_files:
  - path: google_token.json
    description: Gmail and Calendar OAuth2 authorized-user token
  - path: google_client_secret.json
    description: Google OAuth2 Desktop client
metadata:
  hermes:
    tags: [Google, Gmail, Calendar, Contacts, People, Drive, Docs, Sheets, Email, OAuth]
---

# Google Workspace — managed Hermes deployment

Use the repository-managed integrations for Gmail, Calendar, Google Contacts,
Drive, Docs, and Sheets. The services use separately stored least-privilege
OAuth tokens. Contacts uses the People API with read/write access, while Drive,
Docs, and Sheets remain restricted to the app-owned `hermes` folder.

All runtime clients use only Python's standard library. They do **not** import
`googleapiclient`, `google-auth`, or any pip package.

## Routing rules

1. For Gmail, Google Calendar, Google Contacts, People API, Drive, Docs, or
   Sheets requests, use this skill.
2. A request mentioning a contact, contact list, address book, person, phone
   number, or saved email address must use the Contacts client below. Do not
   substitute Drive, Docs, Sheets, or a contact spreadsheet.
3. Never claim Contacts are unavailable before testing the Contacts runtime and
   token with the documented health command.
4. Do **not** switch to `himalaya` merely because a request mentions email only.
5. Do **not** run `pip`, `pip install`, `setup.py`, or `ensurepip`.
6. Use the exact scripts and `/usr/bin/python3`; do not depend on shell `PATH`.
7. If a script is missing, report that **Google Workspace Runtime Repair** must
   be run.
8. Never broaden Drive access or use another Drive tool. Drive, Docs, and Sheets
   operations must go through the folder-bound client described below.

## Exact runtime paths

```bash
GAPI="${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/google_api.py"
DAPI="${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-workspace/scripts/google_drive.py"
CAPI="${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-contacts/scripts/google_contacts.py"

test -f "$GAPI" || { echo "Google Workspace Runtime Repair is required: $GAPI is missing" >&2; exit 1; }
test -f "$DAPI" || { echo "Google Workspace Runtime Repair is required: $DAPI is missing" >&2; exit 1; }
test -f "$CAPI" || { echo "Google Workspace Runtime Repair is required: $CAPI is missing" >&2; exit 1; }
```

Run them only as:

```bash
/usr/bin/python3 "$GAPI"
/usr/bin/python3 "$DAPI"
/usr/bin/python3 "$CAPI"
```

## Gmail and Calendar health check

```bash
/usr/bin/python3 "$GAPI" check
```

A healthy response contains `"authenticated": true`,
`"calendarReachable": true`, and `"runtime": "python-stdlib"`.

## Gmail

```bash
# Search inbox messages from the last 30 days.
/usr/bin/python3 "$GAPI" gmail search "in:inbox newer_than:30d" --max 100

# Search unread messages.
/usr/bin/python3 "$GAPI" gmail search "in:inbox is:unread" --max 50

# Read a full message.
/usr/bin/python3 "$GAPI" gmail get MESSAGE_ID

# List labels.
/usr/bin/python3 "$GAPI" gmail labels

# Send or reply only after explicit user approval.
/usr/bin/python3 "$GAPI" gmail send --to user@example.com --subject "Subject" --body "Body"
/usr/bin/python3 "$GAPI" gmail reply MESSAGE_ID --body "Body"
```

For inbox summaries, search with `in:inbox newer_than:30d`, fetch important or
ambiguous bodies, summarize by priority and topic, state the reviewed count, and
do not modify mail unless explicitly requested.

## Calendar

```bash
# Upcoming events.
/usr/bin/python3 "$GAPI" calendar list

# Explicit date range.
/usr/bin/python3 "$GAPI" calendar list --start 2026-07-15T00:00:00+08:00 --end 2026-07-16T00:00:00+08:00

# Create only after explicit user approval.
/usr/bin/python3 "$GAPI" calendar create --summary "Meeting" --start 2026-07-15T10:00:00+08:00 --end 2026-07-15T10:30:00+08:00
```

Do not create, update, delete, or invite attendees without explicit approval.
Use Asia/Singapore when the user provides no other timezone.

## Google Contacts

Contacts uses a separate read/write token at
`~/.hermes/google_contacts_token.json` and the People API.

### Contacts health check

Run before the first Contacts operation in a conversation:

```bash
/usr/bin/python3 "$CAPI" check
```

A healthy response contains `"contactsReachable": true`,
`"scope": "https://www.googleapis.com/auth/contacts"`, and
`"runtime": "python-stdlib"`.

When the Contacts token is missing, tell the operator to run **Google Workspace
Setup** with `service=contacts`. Do not redirect the user to a spreadsheet and
do not start OAuth from Telegram.

### List, search, and read contacts

These read operations do not require confirmation:

```bash
/usr/bin/python3 "$CAPI" list --max 100
/usr/bin/python3 "$CAPI" search "Ada" --max 25
/usr/bin/python3 "$CAPI" get people/CONTACT_ID
```

Search before acting when a name is ambiguous. Use only a `people/...` resource
name returned by this client; never invent or guess a contact ID.

### Create contacts

Only after explicit user confirmation:

```bash
/usr/bin/python3 "$CAPI" create \
  --given-name "Ada" \
  --family-name "Lovelace" \
  --email "ada@example.com" \
  --phone "+65 6123 4567" \
  --company "Example Ltd" \
  --job-title "Engineer"
```

Multiple `--email`, `--phone`, and `--url` flags are supported.

### Update or clear contact fields

Only after explicit user confirmation. The client fetches the latest People API
metadata and etag before updating:

```bash
/usr/bin/python3 "$CAPI" update people/CONTACT_ID \
  --email "new@example.com" \
  --phone "+65 6987 6543"

/usr/bin/python3 "$CAPI" update people/CONTACT_ID --clear-phones
/usr/bin/python3 "$CAPI" update people/CONTACT_ID --clear-notes
```

Supported writable fields are names, email addresses, phone numbers, company,
job title, notes, birthday, and URLs.

### Delete contacts

Only after explicit user confirmation:

```bash
/usr/bin/python3 "$CAPI" delete people/CONTACT_ID
```

## Drive workspace boundary

Drive authorization is deliberately limited to the non-sensitive `drive.file`
scope. The client creates one app-owned folder named exactly:

```text
hermes
```

The client persists that folder's ID and enforces these rules in code:

- list only direct children of the managed folder;
- create Docs and Sheets directly inside it;
- reject reads, edits, renames, or trash operations when the file is not a direct
  child of the managed folder;
- reject a managed folder that is renamed, trashed, or missing its app marker;
- never search or operate across the user's wider Drive.

Do not bypass these checks, use raw Drive URLs, or substitute another tool.

### Drive workspace health

Run before the first Drive, Docs, or Sheets operation in a conversation:

```bash
/usr/bin/python3 "$DAPI" workspace status
```

A healthy response contains `"ready": true`, folder name `"hermes"`, and
`"boundary": "direct-children-only"`.

When `google_drive_token.json` is missing, tell the operator to run **Google
Workspace Setup** with `service=drive`. Do not start OAuth from Telegram.

### Drive files

```bash
# Ensure the managed folder exists. Safe and idempotent.
/usr/bin/python3 "$DAPI" workspace ensure

# List files only inside hermes.
/usr/bin/python3 "$DAPI" drive list --max 100

# Inspect one managed file's metadata.
/usr/bin/python3 "$DAPI" drive get FILE_ID

# Rename or trash only after an explicit request.
/usr/bin/python3 "$DAPI" drive rename FILE_ID --name "New name"
/usr/bin/python3 "$DAPI" drive trash FILE_ID
```

### Google Docs

```bash
# Create inside hermes.
/usr/bin/python3 "$DAPI" docs create --title "Meeting notes" --text "Initial content"

# Read a managed document.
/usr/bin/python3 "$DAPI" docs get FILE_ID

# Append only when the user asks to update the document.
/usr/bin/python3 "$DAPI" docs append FILE_ID --text $'\nNew section'
```

### Google Sheets

```bash
# Create inside hermes, optionally with initial rows.
/usr/bin/python3 "$DAPI" sheets create --title "Tracker" --range "Sheet1!A1" --values-json '[["Task","Owner"],["Example","J"]]'

# Read a managed range.
/usr/bin/python3 "$DAPI" sheets get FILE_ID --range "Sheet1!A1:Z100"

# Update or append only when explicitly requested.
/usr/bin/python3 "$DAPI" sheets update FILE_ID --range "Sheet1!A1:B2" --values-json '[["Task","Owner"],["Example","J"]]'
/usr/bin/python3 "$DAPI" sheets append FILE_ID --range "Sheet1!A:B" --values-json '[["Next task","J"]]'
```

`--values-json` must be a JSON array of row arrays. Never construct a command
that targets a file ID obtained outside `drive list` or a prior result from this
folder-bound client.

## Operator-managed workflows

- **Google Workspace Setup** manages the separately stored `core`, `contacts`,
  and `drive` authorization domains.
- **Google Workspace Runtime Repair** installs all managed clients and skills,
  restarts Hermes, and validates every authorized service.

The complete browser-only procedures are documented in
`GOOGLE_WORKSPACE_SETUP.md`, `docs/google-contacts.md`, and
`docs/google-drive-workspace.md`.
