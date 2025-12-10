# ui/memos_view.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from .memo_loader import MemoLoader


class MemosView:
    """Handles the memos list view"""

    def __init__(self, container, scrolled_window):
        self.container = container
        self.scrolled_window = scrolled_window
        self.memo_loader = None

        # Setup scroll pagination
        self.scrolled_window.get_vadjustment().connect('value-changed', self.on_scroll)

    def load_memos(self, api, memos, page_token):
        """Initialize and load memos"""
        self.memo_loader = MemoLoader(api, self.container)
        self.memo_loader.page_token = page_token
        self.memo_loader.load_initial(memos)

    def on_scroll(self, adjustment):
        """Handle scroll for pagination"""
        if not self.memo_loader:
            return

        value = adjustment.get_value()
        upper = adjustment.get_upper()
        page_size = adjustment.get_page_size()

        if value + page_size >= upper - 200:
            self.memo_loader.load_more(None)
