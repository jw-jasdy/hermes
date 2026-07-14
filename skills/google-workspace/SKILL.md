---
name: google-workspace
description: "Personal Gmail and Google Calendar through the repository-managed OAuth integration. Always prefer this skill over Himalaya when Google credentials are configured."
version: 1.0.0
platforms: [linux]
required_credential_files:
  - path: google_token.json
    description: Google OAuth2 authorized-user token
  - path: google_client_secret.json
    description: Google OAuth2 Desktop client
metadata:
  hermes:
    tags: [Google, Gmail, Calendar, Email, OAuth]
---

# Google Workspace — managed Hermes deployment

Use the repository-managed Google OAuth integration for Gmail and Calendar.
This deployment is already configured through GitHub Actions; do not start a
new OAuth flow from Telegram unless the user explicitly asks to reauthorize.

## Routing rules

1. For every Gmail or Google Calendar request, use this skill first.
2. Do **not** switch to the `himalaya` skill merely because a request mentions
   email only. Himalaya is an unrelated App Password setup and is not required
   for this deployment.
3. Do **not** run `pip`, `pip install`, `setup.py`, or attempt to alter the
   system Python environment from an agent conversation.
4. Use the fixed commands below. They explicitly select Hermes' Python virtual
   environment and do not depend on shell `python` resolution.
5. When a command fails, report its concise error output. Tell the operator to
   run **Deploy Hermes Agent**, followed by **Google Workspace OAuth → check**.
   Do not recommend replacing OAuth with Himalaya unless the user specifically
   requests an App Password based setup.

## Health check

Run this before the first Gmail or Calendar operation in a conversation:

```bash
hermes-google-workspace check
```

A healthy result contains:

```text
AUTHENTICATED: Gmail and Calendar API checks passed
```

## API command

All Gmail and Calendar operations must use:

```bash
hermes-google-api
```

Never invoke the bundled `google_api.py` with plain `python`.

## Gmail

```bash
# Search inbox messages from the last 30 days.
hermes-google-api gmail search "in:inbox newer_than:30d" --max 100

# Search unread messages.
hermes-google-api gmail search "in:inbox is:unread" --max 50

# Read a full message after obtaining its ID from search results.
hermes-google-api gmail get MESSAGE_ID

# List labels.
hermes-google-api gmail labels

# Send only after explicit user approval.
hermes-google-api gmail send --to user@example.com --subject "Subject" --body "Body"

# Reply only after explicit user approval.
hermes-google-api gmail reply MESSAGE_ID --body "Body"
```

### Inbox-summary procedure

For requests such as “review my Gmail inbox and summarize messages in the last
30 days”:

1. Run the health check.
2. Search with `in:inbox newer_than:30d` and a reasonable maximum, normally
   `--max 100`.
3. Use the returned sender, subject, date, and snippet to group routine mail.
4. Fetch full message bodies with `gmail get` for messages that appear important,
   ambiguous, action-required, financial, travel-related, security-related, or
   time-sensitive.
5. Summarize by priority and topic. Clearly state the number of messages
   reviewed and whether the search reached its maximum result limit.
6. Do not mark messages read, modify labels, reply, send, archive, or delete
   unless the user explicitly requests that action.

## Calendar

```bash
# Upcoming events.
hermes-google-api calendar list

# Explicit date range.
hermes-google-api calendar list --start 2026-07-15T00:00:00+08:00 --end 2026-07-16T00:00:00+08:00

# Create only after explicit user approval.
hermes-google-api calendar create --summary "Meeting" --start 2026-07-15T10:00:00+08:00 --end 2026-07-15T10:30:00+08:00
```

Do not create, update, delete, or invite attendees without explicit user
approval. Use Asia/Singapore when the user does not provide another timezone.

## Operator-managed setup

OAuth setup, repair, checking, and revocation are performed from GitHub Actions:

- **Google Workspace OAuth → provision-client**
- **Google Workspace OAuth → send-auth-link**
- **Google Workspace OAuth → exchange-callback**
- **Google Workspace OAuth → check**
- **Google Workspace OAuth → revoke**

The complete browser-only procedure is documented in
`docs/google-workspace.md` in the deployment repository.
