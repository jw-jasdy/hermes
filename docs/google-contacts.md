# Google Contacts integration

Hermes accesses personal Google Contacts through the People API with:

```text
https://www.googleapis.com/auth/contacts
```

This scope allows reading, creating, updating, and deleting contacts. The
managed skill requires explicit user confirmation before any mutation.

## Setup

1. Add the Contacts scope under **Google Auth Platform → Data Access**.
2. Run **Google Workspace Setup** with:
   - `service=contacts`
   - `action=send-auth-link`
3. Approve the Telegram authorization link.
4. Store the full failed loopback URL temporarily as
   `GOOGLE_OAUTH_CALLBACK_URL`.
5. Run `service=contacts`, `action=exchange-callback`.
6. Delete the temporary secret.
7. Run **Google Workspace Runtime Repair**.

Healthy markers:

```text
GOOGLE_CONTACTS_AUTHENTICATED
GOOGLE_CONTACTS_READY
```

## Supported operations

- list contacts;
- search names, email addresses, phone numbers, and organizations;
- read one contact;
- create a contact;
- update selected fields;
- clear selected fields;
- delete a contact.

Supported writable fields include names, email addresses, phone numbers,
company, job title, notes, birthday, and URLs.

Updates use the latest People API metadata and etag before mutation to avoid
overwriting a contact that changed since it was read.

## Safety behavior

Hermes must:

- ask for confirmation before create, update, clear, or delete;
- search first when a name is ambiguous;
- use a `people/...` resource name returned by the managed Contacts client;
- never guess a contact ID.
