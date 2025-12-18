# ui/connection_view.py
# Connection screen: URL/token input, connect button, credential persistence

from ..utils.connection_handler import ConnectionHandler
from ..utils.settings import Settings


class ConnectionView:
    """Connection screen controller"""

    def __init__(self, url_entry, token_entry, connect_button, status_label):
        self.url_entry = url_entry
        self.token_entry = token_entry
        self.connect_button = connect_button
        self.status_label = status_label
        self.settings = Settings()
        self.on_success_callback = None

        self._load_credentials()
        self.connect_button.connect("clicked", self._on_connect)

    # -------------------------------------------------------------------------
    # CREDENTIALS
    # -------------------------------------------------------------------------

    def _load_credentials(self):
        """Load saved URL and token"""
        url = self.settings.get_server_url() or "https://notes.rishighan.com"
        token = self.settings.get_api_token() or ""
        self.url_entry.set_text(url)
        self.token_entry.set_text(token)

    def _save_credentials(self, url, token):
        """Persist URL and token"""
        self.settings.set_server_url(url)
        self.settings.set_api_token(token)

    # -------------------------------------------------------------------------
    # CONNECT
    # -------------------------------------------------------------------------

    def _on_connect(self, button):
        """Handle connect button"""
        url = self.url_entry.get_text().strip()
        token = self.token_entry.get_text().strip()

        if not url or not token:
            self._show_error("Please enter both URL and token")
            return

        self.connect_button.set_sensitive(False)
        self.status_label.set_markup("<span>Connecting...</span>")

        ConnectionHandler.connect(
            url,
            token,
            on_success=lambda api, memos, page_token, _: self._on_success(
                url, token, api, memos, page_token
            ),
            on_failure=self._on_failure,
        )

    def _on_success(self, url, token, api, memos, page_token):
        """Connection succeeded"""
        self._save_credentials(url, token)
        self.connect_button.set_sensitive(True)
        if self.on_success_callback:
            self.on_success_callback(api, memos, page_token)

    def _on_failure(self, message):
        """Connection failed"""
        self._show_error(f"Connection failed\n<span size='small'>{message}</span>")
        self.connect_button.set_sensitive(True)

    def _show_error(self, message):
        """Display error in status label"""
        self.status_label.set_markup(f'<span foreground="#e01b24">✗ {message}</span>')
