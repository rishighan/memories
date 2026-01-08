# ui/search_handler.py
# Search bar: toggle, debounce, API search

import threading

from gi.repository import GLib


class SearchHandler:
    """Search bar controller"""

    def __init__(self, api, search_entry, search_bar, search_button):
        self.api = api
        self.search_entry = search_entry
        self.search_bar = search_bar
        self.search_button = search_button
        self.on_results_callback = None
        self.last_query = None
        self._search_timeout = None

        # Signals
        self.search_button.connect("toggled", self._on_toggled)
        self.search_entry.connect("search-changed", self._on_changed)
        self.search_entry.connect("stop-search", self._on_stopped)

        # Bind entry to bar
        self.search_bar.connect_entry(self.search_entry)
        self.search_bar.set_key_capture_widget(search_entry.get_root())

    def _on_toggled(self, button):
        """Toggle search bar"""
        active = button.get_active()
        self.search_bar.set_search_mode(active)

        if active:
            self.search_entry.grab_focus()
        else:
            self._clear()

    def _on_stopped(self, entry):
        """Escape pressed"""
        self.search_button.set_active(False)
        self._clear()

    def _on_changed(self, entry):
        """Query changed - debounce and search"""
        query = entry.get_text().strip()

        if query == self.last_query:
            return
        self.last_query = query

        if not query:
            self._clear()
            return

        # Debounce 300ms
        if self._search_timeout:
            try:
                GLib.source_remove(self._search_timeout)
            except Exception:
                pass
            self._search_timeout = None
        self._search_timeout = GLib.timeout_add(300, self._search, query)

    def _search(self, query):
        """Execute search in background"""
        self._search_timeout = None  # Clear since it fired

        def worker():
            success, memos, _ = self.api.search_memos(query)
            GLib.idle_add(self._on_results, query, memos if success else [])

        threading.Thread(target=worker, daemon=True).start()
        return False

    def _on_results(self, query, memos):
        """Deliver results via callback"""
        if self.on_results_callback:
            self.on_results_callback(query, memos)

    def _clear(self):
        """Clear search and restore list"""
        self.search_entry.set_text("")
        self.last_query = None
        if self.on_results_callback:
            self.on_results_callback(None, [])
