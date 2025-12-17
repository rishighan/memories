# ui/memo_heatmap.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk, Gdk, Pango, PangoCairo
import cairo
import calendar
from datetime import datetime, timedelta
from collections import defaultdict


class MemoHeatmap(Gtk.DrawingArea):
    """GitHub-style contribution heatmap for memos"""

    def __init__(self):
        super().__init__()

        self.set_hexpand(True)
        self.set_vexpand(False)
        self.set_size_request(-1, 300)
        self.set_draw_func(self._draw)

        # Data: date -> count
        self.memo_counts = defaultdict(int)
        self.current_month = datetime.now().month
        self.current_year = datetime.now().year

        # Colors (RGBA)
        self.color_empty = (0.85, 0.85, 0.85, 1.0)
        self.color_low = (0.68, 0.87, 0.68, 1.0)
        self.color_medium = (0.15, 0.64, 0.41, 1.0)
        self.color_high = (0.85, 0.65, 0.13, 1.0)

        self._last_height = 300

    def set_memos(self, memos):
        """Process memos and count by date"""
        self.memo_counts.clear()

        for memo in memos:
            create_time = memo.get('createTime', '')
            if create_time:
                try:
                    dt = datetime.fromisoformat(create_time.replace('Z', '+00:00'))
                    date_key = dt.date()
                    self.memo_counts[date_key] += 1
                except:
                    pass

        self.queue_draw()

    def _get_color_for_count(self, count):
        """Get color based on memo count"""
        if count == 0:
            return self.color_empty
        elif count <= 3:
            return self.color_low
        elif count <= 10:
            return self.color_medium
        else:
            return self.color_high

    def _get_text_color_for_count(self, count):
        """Get text color based on background"""
        if count == 0:
            return (0.5, 0.5, 0.5, 1.0)  # Gray for empty
        elif count <= 3:
            return (0.2, 0.4, 0.2, 1.0)  # Dark green
        else:
            return (1.0, 1.0, 1.0, 1.0)  # White for darker backgrounds

    def _draw_rounded_rect(self, cr, x, y, width, height, radius):
        """Draw a rounded rectangle"""
        cr.new_sub_path()
        cr.arc(x + width - radius, y + radius, radius, -1.5708, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, 1.5708)
        cr.arc(x + radius, y + height - radius, radius, 1.5708, 3.14159)
        cr.arc(x + radius, y + radius, radius, 3.14159, 4.71239)
        cr.close_path()

    def _draw(self, area, cr, width, height):
        """Draw the heatmap"""
        cols = 7
        cell_gap = 9
        cell_radius = 15
        padding = 0
        header_height = 80  # Increased for spacing

        # Calculate cell size to fill width
        available_width = width - padding
        cell_size = (available_width - (cols - 1) * cell_gap) / cols

        # Grid width and center
        grid_width = cols * cell_size + (cols - 1) * cell_gap
        x_offset = (width - grid_width) / 2

        # Get days in current month
        num_days = calendar.monthrange(self.current_year, self.current_month)[1]
        first_day = datetime(self.current_year, self.current_month, 1)
        rows = (num_days + first_day.weekday()) // 7 + 1

        # Calculate required height
        grid_height = rows * cell_size + (rows - 1) * cell_gap
        required_height = header_height + grid_height + 20

        if abs(required_height - self._last_height) > 10:
            self._last_height = required_height
            self.set_size_request(-1, int(required_height))
            self.queue_resize()

        # Create Pango layout for text
        pango_context = self.get_pango_context()
        layout = Pango.Layout(pango_context)

        # Draw month label using Pango
        font_desc = Pango.FontDescription()
        font_desc.set_size(18 * Pango.SCALE)
        font_desc.set_weight(Pango.Weight.MEDIUM)
        layout.set_font_description(font_desc)

        month_name = first_day.strftime("This month's activity")
        layout.set_text(month_name, -1)

        cr.set_source_rgba(0.5, 0.5, 0.5, 1.0)
        cr.move_to(x_offset, 10)
        PangoCairo.show_layout(cr, layout)

        # Draw day labels (S M T W T F S) - 20px below month header
        day_labels = ['S', 'M', 'T', 'W', 'T', 'F', 'S']
        font_desc.set_size(10 * Pango.SCALE)
        font_desc.set_weight(Pango.Weight.NORMAL)
        layout.set_font_description(font_desc)

        day_labels_y = 50  # 20px spacing from month header

        cr.set_source_rgba(0.6, 0.6, 0.6, 1.0)
        for i, label in enumerate(day_labels):
            layout.set_text(label, -1)
            ink_rect, logical_rect = layout.get_pixel_extents()
            x = x_offset + i * (cell_size + cell_gap) + (cell_size - logical_rect.width) / 2
            cr.move_to(x, day_labels_y)
            PangoCairo.show_layout(cr, layout)

        # Cells start 20px below day labels
        y_offset = day_labels_y + 35  # 20px spacing from day labels

        # Font for cell numbers
        cell_font_size = max(10, min(16, int(cell_size / 3)))
        font_desc.set_size(cell_font_size * Pango.SCALE)
        font_desc.set_weight(Pango.Weight.MEDIUM)
        layout.set_font_description(font_desc)

        # Draw cells
        day = 1
        for row in range(rows):
            for col in range(cols):
                if row == 0 and col < first_day.weekday():
                    continue
                if day > num_days:
                    break

                # Get count for this day
                date = datetime(self.current_year, self.current_month, day).date()
                count = self.memo_counts.get(date, 0)

                # Draw cell
                x = x_offset + col * (cell_size + cell_gap)
                y = y_offset + row * (cell_size + cell_gap)

                if count > 0:
                    # Filled cell with color
                    color = self._get_color_for_count(count)
                    text_color = self._get_text_color_for_count(count)

                    cr.set_source_rgba(*color)
                    self._draw_rounded_rect(cr, x, y, cell_size, cell_size, cell_radius)
                    cr.fill()

                    # Draw count inside cell
                    display_text = str(count) if count < 100 else "99+"
                    layout.set_text(display_text, -1)
                    ink_rect, logical_rect = layout.get_pixel_extents()
                    text_x = x + (cell_size - logical_rect.width) / 2
                    text_y = y + (cell_size - logical_rect.height) / 2

                    cr.set_source_rgba(*text_color)
                    cr.move_to(text_x, text_y)
                    PangoCairo.show_layout(cr, layout)
                else:
                    # Empty cell - transparent grey with 0.4 opacity
                    cr.set_source_rgba(0.6, 0.6, 0.6, 0.4)
                    self._draw_rounded_rect(cr, x, y, cell_size, cell_size, cell_radius)
                    cr.fill()

                day += 1
