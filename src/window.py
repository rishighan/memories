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
from .ui.memo_edit_view import MemoEditView


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

    # Edit screen children
    memo_edit_content = Gtk.Template.Child()
    memo_edit_title = Gtk.Template.Child()
    edit_back_button = Gtk.Template.Child()
    save_memo_button = Gtk.Template.Child()
    save_spinner = Gtk.Template.Child()
    delete_memo_button = Gtk.Template.Child()
    attach_button = Gtk.Template.Child()

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

        # Initialize edit view
        self.memo_edit_view = MemoEditView(
            self.memo_edit_content,
            self.memo_edit_title,
            self.save_memo_button,
            self.save_spinner,
            self.delete_memo_button,
            self.attach_button
        )
        self.memo_edit_view.on_save_callback = self._on_save_memo
        self.memo_edit_view.on_delete_callback = self._on_delete_memo

        # Connect buttons
        self.new_memo_button.connect('clicked', self._on_new_memo_clicked)
        self.edit_back_button.connect('clicked', self._on_back_clicked)

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

        # Set click callback
        self.memos_view.memo_loader.on_memo_clicked = self._on_memo_clicked
    
    def _on_search_results(self, query, memos):
        """Handle search results"""
        if query is None:
            self.memos_view.restore_all_memos()
        else:
            self.memos_view.show_search_results(memos, query)

    def _on_new_memo_clicked(self, button):
        """Open edit screen for new memo"""
        self.memo_edit_view.load_memo(None)
        self.main_stack.set_visible_child_name('memo_edit')

    def _on_memo_clicked(self, memo):
        """Open edit screen for existing memo"""
        self.memo_edit_view.load_memo(memo)
        self.main_stack.set_visible_child_name('memo_edit')

    def _on_back_clicked(self, button):
        """Go back to memo list"""
        self.main_stack.set_visible_child_name('memos')

    def _on_save_memo(self, memo, text, attachments):
        """Save memo (create or update)"""
        if not text.strip():
            print("Empty memo, not saving")
            self._on_back_clicked(None)
            return

        if not self.api:
            print("No API connection")
            return

        self.memo_edit_view.show_saving()

        # Get existing attachments from the edit view
        existing_attachments = self.memo_edit_view.existing_attachments

        def worker():
            if memo:
                # Update existing memo
                if attachments:
                    success, result = self.api.update_memo_with_attachments(
                        memo.get('name'), text, attachments, existing_attachments
                    )
                else:
                    success, result = self.api.update_memo(memo.get('name'), text)
            else:
                # Create new memo
                if attachments:
                    success, result = self.api.create_memo_with_attachments(text, attachments)
                else:
                    success, result = self.api.create_memo(text)

            def on_complete():
                self.memo_edit_view.hide_saving()

                if success:
                    print("Memo saved successfully!")
                    self._reload_memos()
                    self.main_stack.set_visible_child_name('memos')
                else:
                    print("Failed to save memo")

            GLib.idle_add(on_complete)

        threading.Thread(target=worker, daemon=True).start()

    def _on_delete_memo(self, memo):
        """Delete a memo"""
        if not self.api or not memo:
            return

        memo_name = memo.get('name')

        def worker():
            success = self.api.delete_memo(memo_name)

            def on_complete():
                if success:
                    print("Memo deleted successfully!")
                    self._reload_memos()
                    self.main_stack.set_visible_child_name('memos')
                else:
                    print("Failed to delete memo")

            GLib.idle_add(on_complete)

        threading.Thread(target=worker, daemon=True).start()

    def _reload_memos(self):
        """Reload the memo list"""
        def worker():
            success, memos, page_token = self.api.get_memos()

            def on_complete():
                if success:
                    self.memos_view.memo_loader.page_token = page_token
                    self.memos_view.memo_loader.load_initial(memos)
                    self.memos_view.heatmap.set_memos(memos)
                    self.memos_view.loaded_memos = len(memos)
                    self.memos_view.total_memos = len(memos)
                    if page_token:
                        self.memos_view.total_memos = None
                    self.memos_view._update_count()

            GLib.idle_add(on_complete)

        threading.Thread(target=worker, daemon=True).start()
