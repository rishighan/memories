# ui/memo_loader.py
# Memo list loader: pagination, month grouping, row click handling

from gi.repository import Gtk, GLib
from collections import OrderedDict
from datetime import datetime
import threading

from .memo_row import MemoRow
from .memo_heatmap import MemoHeatmap


class MemoLoader:
    """Load, group, and paginate memos"""

    def __init__(self, api, container):
        self.api = api
        self.container = container
        self.page_token = None
        self.loading_more = False
        self.month_sections = {}
        self.on_reload_complete = None
        self.on_memo_clicked = None

    # -------------------------------------------------------------------------
    # LOAD
    # -------------------------------------------------------------------------

    def load_initial(self, memos):
        """Clear and load initial memos"""
        self._clear_container()
        self.month_sections = {}

        for month, month_memos in self._group_by_month(memos).items():
            self._create_section(month, month_memos)

    def load_more(self, callback):
        """Load next page"""
        if self.loading_more or not self.page_token:
            return

        self.loading_more = True

        def worker():
            success, memos, token = self.api.get_memos(page_token=self.page_token)
            GLib.idle_add(self._on_load_more_complete, success, memos, token, callback)

        threading.Thread(target=worker, daemon=True).start()

    def _on_load_more_complete(self, success, memos, token, callback):
        """Handle load_more result"""
        count = 0
        has_more = False

        if success and memos:
            self.page_token = token
            has_more = token is not None

            for month, month_memos in self._group_by_month(memos).items():
                if month in self.month_sections:
                    # Append to existing section
                    listbox = self.month_sections[month]
                    for memo in month_memos:
                        listbox.append(MemoRow.create(memo, self.api, MemoRow.fetch_attachments))
                        count += 1
                else:
                    # New section
                    self._create_section(month, month_memos)
                    count += len(month_memos)
        else:
            self.page_token = None

        self.loading_more = False
        if callback:
            callback(count, has_more)

    def reload_from_start(self):
        """Reload all memos"""
        def worker():
            success, memos, token = self.api.get_memos()
            GLib.idle_add(self._on_reload_complete, success, memos, token)

        threading.Thread(target=worker, daemon=True).start()

    def _on_reload_complete(self, success, memos, token):
        """Handle reload result"""
        if not success:
            return

        self.page_token = token
        self._clear_container()
        self.month_sections = {}

        for month, month_memos in self._group_by_month(memos).items():
            self._create_section(month, month_memos)

        if self.on_reload_complete:
            self.on_reload_complete(len(memos))

    # -------------------------------------------------------------------------
    # SECTIONS
    # -------------------------------------------------------------------------

    def _create_section(self, month, memos):
        """Create month header + listbox"""
        # Header
        header = Gtk.Label(label=month)
        header.set_xalign(0)
        header.set_margin_top(24)
        header.set_margin_bottom(12)
        header.set_margin_start(20)
        header.set_margin_end(20)
        header.add_css_class('title-3')

        # List
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        listbox.add_css_class('boxed-list')
        listbox.connect('row-activated', self._on_row_activated)

        for memo in memos:
            listbox.append(MemoRow.create(memo, self.api, MemoRow.fetch_attachments))

        self.container.append(header)
        self.container.append(listbox)
        self.month_sections[month] = listbox

    def _group_by_month(self, memos):
        """Group memos by 'Month Year'"""
        grouped = OrderedDict()

        for memo in memos:
            ts = memo.get('createTime', '')
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                key = dt.strftime('%B %Y')
            except:
                key = 'Unknown'

            if key not in grouped:
                grouped[key] = []
            grouped[key].append(memo)

        return grouped

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    def _clear_container(self):
        """Remove all children except heatmap"""
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            if not isinstance(child, MemoHeatmap):
                self.container.remove(child)
            child = next_child

    def _on_row_activated(self, listbox, row):
        """Handle row click"""
        if hasattr(row, 'memo_data') and self.on_memo_clicked:
            self.on_memo_clicked(row.memo_data)
