# Folder-bound Google Drive, Docs, and Sheets

Hermes uses only:

```text
https://www.googleapis.com/auth/drive.file
```

The runtime creates one app-owned folder named `hermes`, stores its ID in
`~/.hermes/google_drive_workspace.json`, and rejects operations outside that
folder.

## Authorization

Use **Actions → Google Workspace Setup**:

1. Select `service=drive` and `action=send-auth-link`.
2. Approve the private Telegram link.
3. Save the complete failed loopback URL temporarily as
   `GOOGLE_OAUTH_CALLBACK_URL`.
4. Run `service=drive` and `action=exchange-callback`.
5. Delete the temporary callback secret.

A successful exchange prints:

```text
DRIVE_WORKSPACE_AUTHENTICATED: app-owned hermes folder is ready.
```

## Security boundary

Every request validates that:

- the managed folder is named `hermes`;
- the folder is not trashed and retains its app marker;
- files are direct children of that folder;
- the requested Google Workspace type matches the command.

The client never searches the wider Drive.

## Runtime

**Google Workspace Runtime Repair** restores and checks the Drive client after
deployments. A healthy run prints:

```text
GOOGLE_DRIVE_FOLDER_READY
```

Normal deployments preserve:

```text
~/.hermes/google_drive_token.json
~/.hermes/google_drive_workspace.json
```

Hermes asks for confirmation before write, rename, edit, or trash operations.
