# ui/memos_view.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from .memo_loader import MemoLoader


class MemosView:
    """Handles the memos list view"""
    
    def __init__(self, container, scrolled_window, memo_count_label=None):
        self.container = container
        self.scrolled_window = scrolled_window
        self.memo_loader = None
        self.memo_count_label = memo_count_label
        self.loaded_memos = 0
        self.total_memos = 0
        
        # Setup scroll pagination
        self.scrolled_window.get_vadjustment().connect('value-changed', self.on_scroll)
    
    def load_memos(self, api, memos, page_token):
        """Initialize and load memos"""
        self.memo_loader = MemoLoader(api, self.container)
        self.memo_loader.page_token = page_token
        self.memo_loader.load_initial(memos)
        
        self.loaded_memos = len(memos)
        # Get total from API or set initial
        self.total_memos = self.loaded_memos  # Will update if we know there's more
        if page_token:  # If there's a next page, we don't know total yet
            self.total_memos = None
        
        self._update_count()
    
    def on_scroll(self, adjustment):
        """Handle scroll for pagination"""
        if not self.memo_loader:
            return

        value = adjustment.get_value()
        upper = adjustment.get_upper()
        page_size = adjustment.get_page_size()

        if value + page_size >= upper - 200:
            self.memo_loader.load_more(self._on_memos_loaded)
    
    def _on_memos_loaded(self, count, has_more):
        """Called when more memos are loaded"""
        self.loaded_memos += count
        
        # Update total if we've reached the end
        if not has_more:
            self.total_memos = self.loaded_memos
        
        self._update_count()
    
    def _update_count(self):
        """Update the memo count label"""
        if self.memo_count_label:
            if self.total_memos is None or self.total_memos != self.loaded_memos:
                # Still loading, show "X of ?" or "X of Y"
                if self.total_memos is None:
                    self.memo_count_label.set_label(f"{self.loaded_memos} memos loaded")
                else:
                    self.memo_count_label.set_label(f"{self.loaded_memos} of {self.total_memos} memos")
            else:
                # All loaded
                self.memo_count_label.set_label(f"{self.loaded_memos} memos")
