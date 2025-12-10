# window.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk, GLib
import threading
from .memos_api import MemosAPI
from .memo_loader import MemoLoader
from .settings import Settings


@Gtk.Template(resource_path='/org/quasars/memories/window.ui')
class MemoriesWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MemoriesWindow'

    main_stack = Gtk.Template.Child()
    url_entry = Gtk.Template.Child()
    token_entry = Gtk.Template.Child()
    connect_button = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    memos_container = Gtk.Template.Child()
    scrolled_window = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Load custom CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_resource('/org/quasars/memories/style.css')
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.settings = Settings()
        self.api = None
        self.memo_loader = None

        # Load saved credentials
        saved_url = self.settings.get_server_url()
        saved_token = self.settings.get_api_token()

        if saved_url:
            self.url_entry.set_text(saved_url)
        else:
            self.url_entry.set_text('https://notes.rishighan.com')

        if saved_token:
            self.token_entry.set_text(saved_token)

        self.connect_button.connect('clicked', self.on_connect_clicked)

        # Connect scroll event for pagination
        adj = self.scrolled_window.get_vadjustment()
        adj.connect('value-changed', self.on_scroll)

    def on_connect_clicked(self, button):
        base_url = self.url_entry.get_text().strip()
        token = self.token_entry.get_text().strip()

        if not base_url or not token:
            self.status_label.set_markup('<span foreground="#e01b24">⚠ Please enter both URL and token</span>')
            return

        self.connect_button.set_sensitive(False)
        self.status_label.set_markup('<span>Connecting...</span>')

        def test_connection():
            api = MemosAPI(base_url, token)
            success, message = api.test_connection()
            if success:
                user_info = api.get_user_info()
                memos_success, memos, page_token = api.get_memos()
                return success, message, user_info, api, memos_success, memos, page_token
            return success, message, None, None, False, [], None

        def on_complete(success, message, user_info, api, memos_success, memos, page_token):
            if success and user_info:
                self.api = api

                # Initialize memo loader
                self.memo_loader = MemoLoader(api, self.memos_container)
                self.memo_loader.page_token = page_token

                # Save credentials
                self.settings.set_server_url(base_url)
                self.settings.set_api_token(token)

                if memos_success:
                    self.memo_loader.load_initial(memos)
                    self.main_stack.set_visible_child_name('memos')
                else:
                    self.status_label.set_markup('<span foreground="#26a269">✓ Connected!</span>\n<span size="small">But failed to load memos</span>')
            elif success:
                self.status_label.set_markup('<span foreground="#26a269">✓ Connected successfully!</span>')
            else:
                self.status_label.set_markup(f'<span foreground="#e01b24">✗ Connection failed</span>\n<span size="small">{message}</span>')
            self.connect_button.set_sensitive(True)

        def worker():
            result = test_connection()
            GLib.idle_add(lambda: on_complete(*result))

        threading.Thread(target=worker, daemon=True).start()

    def on_scroll(self, adjustment):
        """Load more memos when scrolled to bottom"""
        if not self.memo_loader:
            return

        value = adjustment.get_value()
        upper = adjustment.get_upper()
        page_size = adjustment.get_page_size()

        if value + page_size >= upper - 200:
            self.memo_loader.load_more(None)
