# ui/search_handler.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import GLib
import threading


class SearchHandler:
    """Handles search functionality"""
    
    def __init__(self, api, search_entry, search_bar, search_button):
        self.api = api
        self.search_entry = search_entry
        self.search_bar = search_bar
        self.search_button = search_button
        self.on_results_callback = None
        
        # Connect signals
        self.search_button.connect('toggled', self.on_search_toggled)
        self.search_entry.connect('search-changed', self.on_search_changed)
        
        # Bind search bar to button
        self.search_bar.connect_entry(self.search_entry)
        self.search_bar.set_key_capture_widget(search_entry.get_root())
    
    def on_search_toggled(self, button):
        """Toggle search bar visibility"""
        active = button.get_active()
        self.search_bar.set_search_mode(active)
        
        if active:
            self.search_entry.grab_focus()
        else:
            # Clear search when closing
            self.search_entry.set_text('')
    
    def on_search_changed(self, entry):
        """Handle search query changes"""
        query = entry.get_text().strip()
        
        if not query:
            # Empty search - show all memos
            if self.on_results_callback:
                self.on_results_callback(None, [])
            return
        
        # Debounce search
        if hasattr(self, '_search_timeout'):
            GLib.source_remove(self._search_timeout)
        
        self._search_timeout = GLib.timeout_add(300, lambda: self._perform_search(query))
    
    def _perform_search(self, query):
        """Perform the actual search"""
        def worker():
            success, memos, page_token = self.api.search_memos(query)
            
            def on_complete():
                if self.on_results_callback:
                    self.on_results_callback(query, memos if success else [])
            
            GLib.idle_add(on_complete)
        
        threading.Thread(target=worker, daemon=True).start()
        return False  # Remove timeout
