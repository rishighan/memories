# ui/connection_view.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk
from ..utils.connection_handler import ConnectionHandler
from ..utils.settings import Settings


class ConnectionView:
    """Handles the connection screen UI logic"""

    def __init__(self, url_entry, token_entry, connect_button, status_label):
        self.url_entry = url_entry
        self.token_entry = token_entry
        self.connect_button = connect_button
        self.status_label = status_label
        self.settings = Settings()

        self._load_credentials()
        self.connect_button.connect('clicked', self.on_connect_clicked)

        self.on_success_callback = None

    def _load_credentials(self):
        """Load saved credentials"""
        saved_url = self.settings.get_server_url()
        saved_token = self.settings.get_api_token()

        self.url_entry.set_text(saved_url if saved_url else 'https://notes.rishighan.com')
        if saved_token:
            self.token_entry.set_text(saved_token)

    def on_connect_clicked(self, button):
        """Handle connect button click"""
        base_url = self.url_entry.get_text().strip()
        token = self.token_entry.get_text().strip()

        if not base_url or not token:
            self.status_label.set_markup('<span foreground="#e01b24">⚠ Please enter both URL and token</span>')
            return

        self.connect_button.set_sensitive(False)
        self.status_label.set_markup('<span>Connecting...</span>')

        ConnectionHandler.connect(
            base_url,
            token,
            on_success=lambda api, memos, page_token, user_info: self._on_success(
                base_url, token, api, memos, page_token
            ),
            on_failure=self._on_failure
        )

    def _on_success(self, base_url, token, api, memos, page_token):
        """Handle successful connection"""
        # Save credentials
        self.settings.set_server_url(base_url)
        self.settings.set_api_token(token)

        self.connect_button.set_sensitive(True)

        if self.on_success_callback:
            self.on_success_callback(api, memos, page_token)

    def _on_failure(self, message):
        """Handle connection failure"""
        self.status_label.set_markup(
            f'<span foreground="#e01b24">✗ Connection failed</span>\n'
            f'<span size="small">{message}</span>'
        )
        self.connect_button.set_sensitive(True)
