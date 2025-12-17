# ui/memo_heatmap.py
# GitHub-style activity heatmap for current month

from gi.repository import Gtk, Pango, PangoCairo
import calendar
from datetime import datetime
from collections import defaultdict


class MemoHeatmap(Gtk.DrawingArea):
    """Calendar heatmap showing memo activity"""

    # Colors (RGBA)
    COLOR_EMPTY = (0.6, 0.6, 0.6, 0.4)
    COLOR_LOW = (0.68, 0.87, 0.68, 1.0)      # 1-3 memos
    COLOR_MEDIUM = (0.15, 0.64, 0.41, 1.0)   # 4-10 memos
    COLOR_HIGH = (0.85, 0.65, 0.13, 1.0)     # 10+ memos

    def __init__(self):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(False)
        self.set_size_request(-1, 300)
        self.set_draw_func(self._draw)

        self.memo_counts = defaultdict(int)
        self.current_month = datetime.now().month
        self.current_year = datetime.now().year
        self._last_height = 300

    # -------------------------------------------------------------------------
    # DATA
    # -------------------------------------------------------------------------

    def set_memos(self, memos):
        """Count memos by date"""
        self.memo_counts.clear()

        for memo in memos:
            create_time = memo.get('createTime', '')
            if not create_time:
                continue
            try:
                dt = datetime.fromisoformat(create_time.replace('Z', '+00:00'))
                self.memo_counts[dt.date()] += 1
            except:
                pass

        self.queue_draw()

    # -------------------------------------------------------------------------
    # COLORS
    # -------------------------------------------------------------------------

    def _get_cell_color(self, count):
        """Background color based on count"""
        if count == 0:
            return self.COLOR_EMPTY
        if count <= 3:
            return self.COLOR_LOW
        if count <= 10:
            return self.COLOR_MEDIUM
        return self.COLOR_HIGH

    def _get_text_color(self, count):
        """Text color for contrast"""
        if count == 0:
            return (0.5, 0.5, 0.5, 1.0)
        if count <= 3:
            return (0.2, 0.4, 0.2, 1.0)
        return (1.0, 1.0, 1.0, 1.0)

    # -------------------------------------------------------------------------
    # DRAWING
    # -------------------------------------------------------------------------

    def _draw(self, area, cr, width, height):
        """Render the heatmap"""
        cols = 7
        cell_gap = 9
        cell_radius = 15
        header_height = 80

        # Calculate cell size to fill width
        cell_size = (width - (cols - 1) * cell_gap) / cols
        grid_width = cols * cell_size + (cols - 1) * cell_gap
        x_offset = (width - grid_width) / 2

        # Month info
        num_days = calendar.monthrange(self.current_year, self.current_month)[1]
        first_day = datetime(self.current_year, self.current_month, 1)
        first_weekday = first_day.weekday()
        rows = (num_days + first_weekday) // 7 + 1

        # Resize if needed
        grid_height = rows * cell_size + (rows - 1) * cell_gap
        required_height = header_height + grid_height + 20
        if abs(required_height - self._last_height) > 10:
            self._last_height = required_height
            self.set_size_request(-1, int(required_height))
            self.queue_resize()

        # Pango setup
        layout = Pango.Layout(self.get_pango_context())
        font = Pango.FontDescription()

        # Month header
        font.set_size(18 * Pango.SCALE)
        font.set_weight(Pango.Weight.MEDIUM)
        layout.set_font_description(font)
        layout.set_text("This month's activity", -1)
        cr.set_source_rgba(0.5, 0.5, 0.5, 1.0)
        cr.move_to(x_offset, 10)
        PangoCairo.show_layout(cr, layout)

        # Day labels (S M T W T F S)
        font.set_size(10 * Pango.SCALE)
        font.set_weight(Pango.Weight.NORMAL)
        layout.set_font_description(font)
        cr.set_source_rgba(0.6, 0.6, 0.6, 1.0)

        day_labels_y = 50
        for i, label in enumerate(['S', 'M', 'T', 'W', 'T', 'F', 'S']):
            layout.set_text(label, -1)
            _, logical = layout.get_pixel_extents()
            x = x_offset + i * (cell_size + cell_gap) + (cell_size - logical.width) / 2
            cr.move_to(x, day_labels_y)
            PangoCairo.show_layout(cr, layout)

        # Cell font
        cell_font_size = max(10, min(16, int(cell_size / 3)))
        font.set_size(cell_font_size * Pango.SCALE)
        font.set_weight(Pango.Weight.MEDIUM)
        layout.set_font_description(font)

        # Draw cells
        y_offset = day_labels_y + 35
        day = 1

        for row in range(rows):
            for col in range(cols):
                # Skip empty cells before first day
                if row == 0 and col < first_weekday:
                    continue
                if day > num_days:
                    break

                date = datetime(self.current_year, self.current_month, day).date()
                count = self.memo_counts.get(date, 0)

                x = x_offset + col * (cell_size + cell_gap)
                y = y_offset + row * (cell_size + cell_gap)

                # Cell background
                cr.set_source_rgba(*self._get_cell_color(count))
                self._draw_rounded_rect(cr, x, y, cell_size, cell_size, cell_radius)
                cr.fill()

                # Cell count (only if > 0)
                if count > 0:
                    text = str(count) if count < 100 else "99+"
                    layout.set_text(text, -1)
                    _, logical = layout.get_pixel_extents()
                    tx = x + (cell_size - logical.width) / 2
                    ty = y + (cell_size - logical.height) / 2
                    cr.set_source_rgba(*self._get_text_color(count))
                    cr.move_to(tx, ty)
                    PangoCairo.show_layout(cr, layout)

                day += 1

    def _draw_rounded_rect(self, cr, x, y, w, h, r):
        """Draw rounded rectangle path"""
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -1.5708, 0)
        cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
        cr.arc(x + r, y + h - r, r, 1.5708, 3.14159)
        cr.arc(x + r, y + r, r, 3.14159, 4.71239)
        cr.close_path()
