# ui/memos_view.py
# Memo list: heatmap, pagination, search

from gi.repository import GLib, Gtk

from .memo_heatmap import MemoHeatmap
from .memo_loader import MemoLoader
from .memo_row import MemoRow


class MemosView:
    """Memo list with heatmap and search"""

    def __init__(self, container, scrolled_window, memo_count_label=None):
        self.container = container
        self.scrolled_window = scrolled_window
        self.memo_count_label = memo_count_label
        self.memo_loader = None
        self.heatmap = None
        self.loaded_memos = 0
        self.total_memos = 0
        self.is_searching = False

        self.adjustment = self.scrolled_window.get_vadjustment()
        self.adjustment.connect("value-changed", self._on_scroll)

    # -------------------------------------------------------------------------
    # LOAD
    # -------------------------------------------------------------------------

    def load_memos(self, api, memos, page_token):
        """Load memos with heatmap"""
        # Fresh heatmap
        if self.heatmap and self.heatmap.get_parent():
            self.container.remove(self.heatmap)

        self.heatmap = MemoHeatmap()
        self.heatmap.set_margin_start(20)
        self.heatmap.set_margin_end(20)
        self.heatmap.set_margin_top(20)
        self.heatmap.set_margin_bottom(20)
        self.container.prepend(self.heatmap)
        self.heatmap.set_memos(memos)

        self.memo_loader = MemoLoader(api, self.container)
        self.memo_loader.page_token = page_token
        self.memo_loader.load_initial(memos)

        self.loaded_memos = len(memos)
        self.total_memos = len(memos) if not page_token else None
        self.is_searching = False
        self._update_count()

        GLib.timeout_add(100, self._scroll_past_heatmap)

    def _scroll_past_heatmap(self):
        """Hide heatmap initially"""
        if self.heatmap:
            h = self.heatmap.get_allocated_height()
            m = self.heatmap.get_margin_top() + self.heatmap.get_margin_bottom()
            self.adjustment.set_value(h + m)
        return False

    # -------------------------------------------------------------------------
    # SCROLL
    # -------------------------------------------------------------------------

    def _on_scroll(self, adjustment):
        """Heatmap fade + pagination"""
        value = adjustment.get_value()
        upper = adjustment.get_upper()
        page_size = adjustment.get_page_size()

        if self.heatmap:
            opacity = max(0.3, 1.0 - (value / 100.0) * 0.7) if value <= 100 else 0.3
            self.heatmap.set_opacity(opacity)

        if self.memo_loader and not self.is_searching:
            if value + page_size >= upper - 200:
                self.memo_loader.load_more(self._on_memos_loaded)

    def _on_memos_loaded(self, count, has_more):
        """After loading more"""
        self.loaded_memos += count
        if not has_more:
            self.total_memos = self.loaded_memos
        self._update_count()

    # -------------------------------------------------------------------------
    # SEARCH
    # -------------------------------------------------------------------------

    def show_search_results(self, memos, query):
        """Show search results"""
        self.is_searching = True

        # Clear
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

        if memos:
            header = Gtk.Label(label=f"Search results for '{query}'")
            header.set_xalign(0)
            header.set_margin_top(24)
            header.set_margin_bottom(12)
            header.set_margin_start(20)
            header.set_margin_end(20)
            header.add_css_class("title-3")
            self.container.append(header)

            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
            listbox.add_css_class("boxed-list")
            listbox.connect("row-activated", self._on_search_row_activated)

            for memo in memos:
                row = MemoRow.create(
                    memo, self.memo_loader.api, MemoRow.fetch_attachments
                )
                row.memo_data = memo
                listbox.append(row)

            self.container.append(listbox)
        else:
            label = Gtk.Label(label=f"No results found for '{query}'")
            label.set_margin_top(48)
            label.add_css_class("dim-label")
            self.container.append(label)

        self.loaded_memos = len(memos)
        self.total_memos = len(memos)
        self._update_count()

    def _on_search_row_activated(self, listbox, row):
        """Handle search result click"""
        if hasattr(row, "memo_data") and self.memo_loader.on_memo_clicked:
            self.memo_loader.on_memo_clicked(row.memo_data)

    def restore_all_memos(self):
        """Restore full list"""
        if not self.memo_loader:
            return

        self.is_searching = False

        if self.heatmap and not self.heatmap.get_parent():
            self.container.prepend(self.heatmap)

        def on_reload(count):
            self.loaded_memos = count
            self.total_memos = count if not self.memo_loader.page_token else None
            self._update_count()

        self.memo_loader.on_reload_complete = on_reload
        self.memo_loader.reload_from_start()

    # -------------------------------------------------------------------------
    # COUNT
    # -------------------------------------------------------------------------

    def _update_count(self):
        """Update count label"""
        if not self.memo_count_label:
            return

        if self.total_memos is None:
            self.memo_count_label.set_label(f"{self.loaded_memos} memos loaded")
        elif self.total_memos != self.loaded_memos:
            self.memo_count_label.set_label(
                f"{self.loaded_memos} of {self.total_memos} memos"
            )
        else:
            self.memo_count_label.set_label(f"{self.loaded_memos} memos")
