# memo_loader.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk, GLib
import threading
from collections import OrderedDict
import datetime
from .memo_row import MemoRow


class MemoLoader:
    """Handles loading and organizing memos"""

    def __init__(self, api, container):
        self.api = api
        self.container = container
        self.page_token = None
        self.loading_more = False
        self.month_sections = {}

    def load_initial(self, memos):
        """Load initial memos, clearing container"""
        # Clear existing
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

        self.month_sections = {}
        grouped = self._group_by_month(memos)

        for month_year, month_memos in grouped.items():
            self._create_month_section(month_year, month_memos)

        print(f"Loaded {len(memos)} initial memos")

    def load_more(self, callback):
        """Load next page of memos"""
        if self.loading_more or not self.page_token:
            return

        self.loading_more = True
        print("Loading more memos...")

        def worker():
            success, memos, page_token = self.api.get_memos(page_token=self.page_token)

            def on_complete():
                loaded_count = 0
                has_more = False

                if success and memos:
                    self.page_token = page_token
                    has_more = page_token is not None

                    grouped = self._group_by_month(memos)

                    for month_year, month_memos in grouped.items():
                        if month_year in self.month_sections:
                            listbox = self.month_sections[month_year]
                            for memo in month_memos:
                                row = MemoRow.create(memo, self.api, MemoRow.fetch_attachments)
                                listbox.append(row)
                                loaded_count += 1
                        else:
                            self._create_month_section(month_year, month_memos)
                            loaded_count += len(month_memos)

                    print(f"Loaded {loaded_count} more memos")
                else:
                    print("No more memos to load")
                    self.page_token = None

                self.loading_more = False
                if callback:
                    callback(loaded_count, has_more)

            GLib.idle_add(on_complete)

        threading.Thread(target=worker, daemon=True).start()
    def _group_by_month(self, memos):
        """Group memos by month and year"""
        grouped = OrderedDict()

        for memo in memos:
            created_ts = memo.get('createTime', '')
            if created_ts:
                try:
                    dt = datetime.datetime.fromisoformat(created_ts.replace('Z', '+00:00'))
                    month_year = dt.strftime('%B %Y')

                    if month_year not in grouped:
                        grouped[month_year] = []
                    grouped[month_year].append(memo)
                except:
                    if "Unknown" not in grouped:
                        grouped["Unknown"] = []
                    grouped["Unknown"].append(memo)

        return grouped

    def _create_month_section(self, month_year, memos):
        """Create a section with header and list for a month"""
        # Month header label
        header = Gtk.Label(label=month_year)
        header.set_xalign(0)
        header.set_margin_top(24)
        header.set_margin_bottom(12)
        header.set_margin_start(20)
        header.set_margin_end(20)
        header.add_css_class('title-3')

        # ListBox for this month's memos
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.add_css_class('boxed-list')

        for memo in memos:
            row = MemoRow.create(memo, self.api, MemoRow.fetch_attachments)
            listbox.append(row)

        # Add to container
        self.container.append(header)
        self.container.append(listbox)

        # Track this section
        self.month_sections[month_year] = listbox
