# window.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk, GLib
import threading
from .ui.connection_view import ConnectionView
from .ui.memos_view import MemosView
from .ui.search_handler import SearchHandler
from .ui.new_memo_dialog import NewMemoDialog


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
    search_entry = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    search_button = Gtk.Template.Child()
    new_memo_button = Gtk.Template.Child()

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

        # Initialize API
        self.api = None

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

        self.search_handler = None

        # Create new memo dialog programmatically
        self.new_memo_dialog = NewMemoDialog()
        self.new_memo_dialog.on_save_callback = self.on_save_memo

        # Connect new memo button
        self.new_memo_button.connect('clicked', self.on_new_memo_clicked)

        # Connect views
        self.connection_view.on_success_callback = self._on_connected

    def _on_connected(self, api, memos, page_token):
        """Handle successful connection"""
        self.api = api
        # Update status bar
        self.server_label.set_label(f"Connected to {api.base_url}")
        self.connection_status_label.set_label("●")
        self.connection_status_label.set_tooltip_text("Connected")
        self.memo_count_label.set_label(f"{len(memos)} memos")

        # Initialize search
        self.search_handler = SearchHandler(
            api,
            self.search_entry,
            self.search_bar,
            self.search_button
        )
        self.search_handler.on_results_callback = self._on_search_results

        # Load memos and switch view
        self.memos_view.load_memos(api, memos, page_token)
        self.main_stack.set_visible_child_name('memos')
    
    def _on_search_results(self, query, memos):
        """Handle search results"""
        if query is None:
            # Restore all memos
            self.memos_view.restore_all_memos()
        else:
            # Show search results
            self.memos_view.show_search_results(memos, query)

    def on_new_memo_clicked(self, button):
        """Open new memo dialog"""
        self.new_memo_dialog.present(self)

    def on_save_memo(self, text):
        """Save the new memo"""
        if not text.strip():
            print("Empty memo, not saving")
            self.new_memo_dialog.close()
            return

        if not self.api:
            print("No API connection")
            return

        # Show saving spinner
        self.new_memo_dialog.show_saving()

        # Get attachments
        attachments = self.new_memo_dialog.attachments.copy()

        def worker():
            # Upload attachments first
            resource_names = []
            for attachment in attachments:
                success, resource_name = self.api.upload_file(attachment['file'].get_path())
                if success:
                    resource_names.append(resource_name)

            # Append resource references to content
            content = text
            if resource_names:
                content += '\n\n'
                for resource_name in resource_names:
                    content += f'![](/{resource_name})\n'

            # Create memo
            success, memo = self.api.create_memo(content)

            def on_complete():
                self.new_memo_dialog.hide_saving()

                if success:
                    print("Memo saved successfully!")

                    # Clear everything
                    self.new_memo_dialog.clear()
                    self.new_memo_dialog.close()

                    # Reload memos
                    self._reload_memos()
                else:
                    print("Failed to save memo")

            GLib.idle_add(on_complete)

        threading.Thread(target=worker, daemon=True).start()

    def _reload_memos(self):
        """Reload the memo list from scratch"""
        def worker():
            success, memos, page_token = self.api.get_memos()

            def on_complete():
                if success:
                    self.memos_view.memo_loader.page_token = page_token
                    self.memos_view.memo_loader.load_initial(memos)
                    self.memos_view.loaded_memos = len(memos)
                    self.memos_view.total_memos = len(memos)
                    if page_token:
                        self.memos_view.total_memos = None
                    self.memos_view._update_count()

            GLib.idle_add(on_complete)

        threading.Thread(target=worker, daemon=True).start()
