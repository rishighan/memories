# window.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk
from .ui.connection_view import ConnectionView
from .ui.memos_view import MemosView


@Gtk.Template(resource_path='/org/quasars/memories/window.ui')
class MemoriesWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MemoriesWindow'

    # Template children
    main_stack = Gtk.Template.Child()
    url_entry = Gtk.Template.Child()
    token_entry = Gtk.Template.Child()
    connect_button = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    memos_container = Gtk.Template.Child()
    scrolled_window = Gtk.Template.Child()
    server_label = Gtk.Template.Child()
    connection_status_label = Gtk.Template.Child()
    memo_count_label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Load CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_resource('/org/quasars/memories/style.css')
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Initialize views
        self.connection_view = ConnectionView(
            self.url_entry,
            self.token_entry,
            self.connect_button,
            self.status_label
        )

        self.memos_view = MemosView(
            self.memos_container,
            self.scrolled_window,
            self.memo_count_label
        )

        # Connect views
        self.connection_view.on_success_callback = self._on_connected

    def _on_connected(self, api, memos, page_token):
        """Handle successful connection"""
        # Update status bar
        self.server_label.set_label(f"Connected to {api.base_url}")
        self.connection_status_label.set_label("●")
        self.connection_status_label.set_tooltip_text("Connected")
        self.memo_count_label.set_label(f"{len(memos)} memos")

        # Load memos and switch view
        self.memos_view.load_memos(api, memos, page_token)
        self.main_stack.set_visible_child_name('memos')
