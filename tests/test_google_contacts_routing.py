from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SKILL = ROOT / "skills" / "google-workspace" / "SKILL.md"


class GoogleContactsRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = WORKSPACE_SKILL.read_text(encoding="utf-8")

    def test_primary_google_skill_advertises_contacts(self) -> None:
        self.assertIn("Gmail, Calendar, Contacts", self.skill)
        self.assertIn("Contacts, People", self.skill)

    def test_contacts_requests_use_people_client(self) -> None:
        self.assertIn('CAPI="${HERMES_HOME:-$HOME/.hermes}/skills/productivity/google-contacts/scripts/google_contacts.py"', self.skill)
        self.assertIn('/usr/bin/python3 "$CAPI" list --max 100', self.skill)
        self.assertIn('/usr/bin/python3 "$CAPI" search "Ada" --max 25', self.skill)

    def test_skill_forbids_spreadsheet_fallback(self) -> None:
        self.assertIn("Do not\n   substitute Drive, Docs, Sheets, or a contact spreadsheet", self.skill)
        self.assertIn("Never claim Contacts are unavailable", self.skill)

    def test_contact_mutations_require_confirmation(self) -> None:
        self.assertGreaterEqual(self.skill.count("Only after explicit user confirmation"), 3)

    def test_removed_workflow_names_do_not_return(self) -> None:
        self.assertNotIn("Google Workspace OAuth", self.skill)
        self.assertNotIn("Google Drive Workspace OAuth", self.skill)
        self.assertIn("Google Workspace Setup", self.skill)


if __name__ == "__main__":
    unittest.main()
