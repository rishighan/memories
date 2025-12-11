# ui/memos_view.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk
from .memo_loader import MemoLoader
from .memo_row import MemoRow


class MemosView:
    """Handles the memos list view"""
    
    def __init__(self, container, scrolled_window, memo_count_label=None):
        self.container = container
        self.scrolled_window = scrolled_window
        self.memo_loader = None
        self.memo_count_label = memo_count_label
        self.loaded_memos = 0
        self.total_memos = 0
        self.is_searching = False
        
        # Setup scroll pagination
        self.scrolled_window.get_vadjustment().connect('value-changed', self.on_scroll)
    
    def load_memos(self, api, memos, page_token):
        """Initialize and load memos"""
        self.memo_loader = MemoLoader(api, self.container)
        self.memo_loader.page_token = page_token
        self.memo_loader.load_initial(memos)
        
        self.loaded_memos = len(memos)
        self.total_memos = self.loaded_memos
        if page_token:
            self.total_memos = None
        
        self.is_searching = False
        self._update_count()
    
    def on_scroll(self, adjustment):
        """Handle scroll for pagination"""
        if not self.memo_loader or self.is_searching:
            return

        value = adjustment.get_value()
        upper = adjustment.get_upper()
        page_size = adjustment.get_page_size()

        if value + page_size >= upper - 200:
            self.memo_loader.load_more(self._on_memos_loaded)
    
    def _on_memos_loaded(self, count, has_more):
        """Called when more memos are loaded"""
        self.loaded_memos += count
        
        if not has_more:
            self.total_memos = self.loaded_memos
        
        self._update_count()
    
    def _update_count(self):
        """Update the memo count label"""
        if self.memo_count_label:
            if self.total_memos is None or self.total_memos != self.loaded_memos:
                if self.total_memos is None:
                    self.memo_count_label.set_label(f"{self.loaded_memos} memos loaded")
                else:
                    self.memo_count_label.set_label(f"{self.loaded_memos} of {self.total_memos} memos")
            else:
                self.memo_count_label.set_label(f"{self.loaded_memos} memos")
    
    def show_search_results(self, memos, query):
        """Display search results"""
        self.is_searching = True
        
        # Clear container
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child
        
        # Add search results
        if memos:
            header = Gtk.Label(label=f"Search results for '{query}'")
            header.set_xalign(0)
            header.set_margin_top(24)
            header.set_margin_bottom(12)
            header.set_margin_start(20)
            header.set_margin_end(20)
            header.add_css_class('title-3')
            self.container.append(header)
            
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            listbox.add_css_class('boxed-list')
            
            for memo in memos:
                row = MemoRow.create(memo, self.memo_loader.api, MemoRow.fetch_attachments)
                listbox.append(row)
            
            self.container.append(listbox)
        else:
            no_results = Gtk.Label(label=f"No results found for '{query}'")
            no_results.set_margin_top(48)
            no_results.add_css_class('dim-label')
            self.container.append(no_results)
        
        # Update count
        self.total_memos = len(memos)
        self.loaded_memos = len(memos)
        self._update_count()
    
    def restore_all_memos(self):
        """Restore the full memo list after search"""
        if self.memo_loader:
            self.is_searching = False
            # Reload from the beginning
            self.memo_loader.reload_from_start()
