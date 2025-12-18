# ui/preferences.py
# Preferences window: server credentials, app settings

from gi.repository import Adw, Gtk

from ..utils.settings import Settings


class PreferencesWindow(Adw.PreferencesWindow):
    """App preferences"""

    def __init__(self, parent, on_credentials_changed=None):
        super().__init__()
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_title("Preferences")
        self.set_default_size(400, 350)  # Smaller size
        self.settings = Settings()
        self.on_credentials_changed = on_credentials_changed

        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        """Build preferences UI"""
        # Server page
        page = Adw.PreferencesPage()
        page.set_title("Server")
        page.set_icon_name("network-server-symbolic")
        self.add(page)

        # Credentials group
        creds_group = Adw.PreferencesGroup()
        creds_group.set_title("Memos Server")
        creds_group.set_description("Connect to your Memos instance")
        page.add(creds_group)

        # Server URL
        self.url_row = Adw.EntryRow()
        self.url_row.set_title("Server URL")
        self.url_row.connect("changed", self._on_changed)
        creds_group.add(self.url_row)

        # API Token
        self.token_row = Adw.PasswordEntryRow()
        self.token_row.set_title("API Token")
        self.token_row.connect("changed", self._on_changed)
        creds_group.add(self.token_row)

        # Test connection button
        test_button = Gtk.Button(label="Test Connection")
        test_button.add_css_class("suggested-action")
        test_button.set_margin_top(12)
        test_button.connect("clicked", self._on_test_clicked)
        creds_group.add(test_button)

        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_margin_top(8)
        self.status_label.set_visible(False)
        creds_group.add(self.status_label)

    def _load_settings(self):
        """Load saved credentials"""
        url = self.settings.get_server_url() or ""
        token = self.settings.get_api_token() or ""
        self.url_row.set_text(url)
        self.token_row.set_text(token)

    def _on_changed(self, row):
        """Save on change"""
        self.settings.set_server_url(self.url_row.get_text().strip())
        self.settings.set_api_token(self.token_row.get_text().strip())

    def _on_test_clicked(self, button):
        """Test connection"""
        from ..api.memos_api import MemosAPI

        url = self.url_row.get_text().strip()
        token = self.token_row.get_text().strip()

        if not url or not token:
            self._show_status("Enter URL and token", error=True)
            return

        button.set_sensitive(False)
        self._show_status("Connecting...")

        api = MemosAPI(url, token)
        success, message = api.test_connection()

        if success:
            self._show_status("Connected!", error=False)
            if self.on_credentials_changed:
                self.on_credentials_changed()
        else:
            self._show_status(f"Failed: {message}", error=True)

        button.set_sensitive(True)

    def _show_status(self, message, error=False):
        """Show status message"""
        self.status_label.set_label(message)
        self.status_label.set_visible(True)
        if error:
            self.status_label.add_css_class("error")
            self.status_label.remove_css_class("success")
        else:
            self.status_label.add_css_class("success")
            self.status_label.remove_css_class("error")
