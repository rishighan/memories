# ui/memo_row.py
# Memo list row: content preview, thumbnail stack, async image loading

from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Pango
from datetime import datetime
import threading
import requests


class MemoRow:
    """Factory for memo list rows"""

    THUMB_SIZE = 160

    # -------------------------------------------------------------------------
    # CREATE ROW
    # -------------------------------------------------------------------------

    @staticmethod
    def create(memo, api, fetch_callback):
        """Build a memo row with optional thumbnail"""
        row = Gtk.ListBoxRow()
        row.set_activatable(True)
        row.memo_data = memo

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Thumbnail
        images = MemoRow._get_image_attachments(memo)
        if images:
            thumb = MemoRow._create_thumbnail(memo, api, fetch_callback, images)
            box.append(thumb)

        # Content
        box.append(MemoRow._create_content(memo))

        # Arrow
        arrow = Gtk.Image.new_from_icon_name('go-next-symbolic')
        arrow.set_valign(Gtk.Align.CENTER)
        box.append(arrow)

        row.set_child(box)
        return row

    # -------------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_image_attachments(memo):
        """Extract image attachments from memo"""
        attachments = memo.get('resources', []) or memo.get('attachments', [])
        return [a for a in attachments if a.get('type', '').startswith('image/')]

    @staticmethod
    def _create_content(memo):
        """Create text content box"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_hexpand(True)

        # Text preview
        content = memo.get('content', '')[:200]
        if len(memo.get('content', '')) > 200:
            content += '...'

        label = Gtk.Label(label=content)
        label.set_xalign(0)
        label.set_wrap(True)
        label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_max_width_chars(50)
        box.append(label)

        # Date
        create_time = memo.get('createTime', '')
        if create_time:
            try:
                dt = datetime.fromisoformat(create_time.replace('Z', '+00:00'))
                date_str = dt.strftime('%B %d, %Y at %I:%M %p')
                date_label = Gtk.Label(label=date_str)
                date_label.set_xalign(0)
                date_label.add_css_class('caption')
                date_label.add_css_class('dim-label')
                box.append(date_label)
            except:
                pass

        return box

    @staticmethod
    def _create_thumbnail(memo, api, fetch_callback, images):
        """Create thumbnail with badge for multiple images"""
        size = MemoRow.THUMB_SIZE

        # Base thumbnail box
        overlay = Gtk.Overlay()

        base_box = Gtk.Box()
        base_box.set_size_request(size, size)
        base_box.add_css_class("thumbnail")

        base_picture = Gtk.Picture()
        base_picture.set_size_request(size, size)
        base_picture.set_can_shrink(True)
        base_picture.add_css_class("thumbnail")

        base_box.append(base_picture)
        overlay.set_child(base_box)

        # Count badge only (no stack indicators)
        if len(images) > 1:
            badge_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            badge_box.set_halign(Gtk.Align.END)
            badge_box.set_valign(Gtk.Align.END)
            badge_box.set_margin_end(8)
            badge_box.set_margin_bottom(8)
            badge_box.add_css_class("osd")

            badge = Gtk.Label(label=f"+{len(images) - 1}")
            badge.add_css_class("heading")
            badge.set_margin_start(8)
            badge.set_margin_end(8)
            badge.set_margin_top(4)
            badge.set_margin_bottom(4)

            badge_box.append(badge)
            overlay.add_overlay(badge_box)

        fetch_callback(base_box, base_picture, memo.get('name', ''), api)
        return overlay

    # -------------------------------------------------------------------------
    # ASYNC IMAGE LOADING
    # -------------------------------------------------------------------------

    @staticmethod
    def fetch_attachments(image_box, placeholder, memo_name, api):
        """Fetch first attachment and load thumbnail"""
        def worker():
            attachments = api.get_memo_attachments(memo_name)
            if not attachments:
                return

            first = attachments[0]
            if 'image' not in first.get('type', '').lower():
                return

            name = first.get('name', '')
            filename = first.get('filename', '')
            if name and filename:
                url = f"/file/{name}/{filename}"
                GLib.idle_add(MemoRow._load_thumbnail, image_box, placeholder, url, api)

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _load_thumbnail(image_box, placeholder, url, api):
        """Load image from URL"""
        def worker():
            try:
                full_url = f"{api.base_url}{url}" if url.startswith('/') else url
                headers = api.headers.copy()
                headers['Accept'] = 'image/*'

                r = requests.get(full_url, headers=headers, timeout=5)
                if r.status_code != 200:
                    return

                content_type = r.headers.get('Content-Type', '')
                if 'image' not in content_type:
                    return

                GLib.idle_add(MemoRow._set_thumbnail, image_box, placeholder, r.content)
            except:
                pass

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _set_thumbnail(image_box, placeholder, data):
        """Set thumbnail from image data"""
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(data)
            loader.close()
            pixbuf = loader.get_pixbuf()

            # Crop to square
            w, h = pixbuf.get_width(), pixbuf.get_height()
            size = min(w, h)
            x, y = (w - size) // 2, (h - size) // 2
            cropped = GdkPixbuf.Pixbuf.new_subpixbuf(pixbuf, x, y, size, size)

            # Scale
            thumb = cropped.scale_simple(MemoRow.THUMB_SIZE, MemoRow.THUMB_SIZE, GdkPixbuf.InterpType.BILINEAR)
            texture = Gdk.Texture.new_for_pixbuf(thumb)

            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_size_request(MemoRow.THUMB_SIZE, MemoRow.THUMB_SIZE)
            picture.set_can_shrink(False)
            picture.add_css_class('thumbnail')

            image_box.remove(placeholder)
            image_box.append(picture)
            image_box.set_visible(True)
        except:
            pass
