# ui/memo_row.py
# Memo list row: content preview, thumbnail stack, async image loading

import contextlib
import threading
from datetime import datetime

import requests
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

from ..utils.markdown import MarkdownUtils


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
        arrow = Gtk.Image.new_from_icon_name("go-next-symbolic")
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
        attachments = memo.get("resources", []) or memo.get("attachments", [])
        return [a for a in attachments if a.get("type", "").startswith("image/")]

    @staticmethod
    def _create_content(memo):
        """Create text content box"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_hexpand(True)

        # Text preview with markdown
        content = memo.get("content", "")[:200]
        if len(memo.get("content", "")) > 200:
            content += "..."

        # Convert markdown to Pango markup
        markup = MarkdownUtils.to_pango_markup(content)

        label = Gtk.Label()
        label.set_markup(markup)
        label.set_xalign(0)
        label.set_wrap(True)
        label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label.set_max_width_chars(50)
        box.append(label)

        # Date with visibility icons
        create_time = memo.get("createTime", "")
        if create_time:
            try:
                dt = datetime.fromisoformat(create_time.replace("Z", "+00:00"))
                date_str = dt.strftime("%B %d, %Y at %I:%M %p")
                
                # Create horizontal box for date and icons
                date_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                date_box.set_halign(Gtk.Align.START)
                
                date_label = Gtk.Label(label=date_str)
                date_label.set_xalign(0)
                date_label.add_css_class("caption")
                date_label.add_css_class("dim-label")
                date_box.append(date_label)
                
                # Add visibility icon
                visibility = memo.get("visibility", "PUBLIC")
                if visibility == "PRIVATE":
                    private_icon = Gtk.Image.new_from_icon_name("system-lock-screen-symbolic")
                    private_icon.set_tooltip_text("Private")
                    private_icon.add_css_class("dim-label")
                    date_box.append(private_icon)
                elif visibility == "PROTECTED":
                    protected_icon = Gtk.Image.new_from_icon_name("dialog-password-symbolic")
                    protected_icon.set_tooltip_text("Protected")
                    protected_icon.add_css_class("dim-label")
                    date_box.append(protected_icon)
                
                box.append(date_box)
            except (ValueError, AttributeError):
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

        fetch_callback(base_box, base_picture, memo.get("name", ""), api)
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
            if "image" not in first.get("type", "").lower():
                return

            name = first.get("name", "")
            filename = first.get("filename", "")
            if name and filename:
                url = f"/file/{name}/{filename}"
                GLib.idle_add(MemoRow._load_thumbnail, image_box, placeholder, url, api)

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _load_thumbnail(image_box, placeholder, url, api):
        """Load image from URL"""

        def worker():
            try:
                full_url = f"{api.base_url}{url}" if url.startswith("/") else url
                print(f"[THUMB] Loading: {full_url}")

                # Copy headers from API - works with both dict and session headers
                headers = {}
                if hasattr(api.headers, 'items'):
                    headers.update(api.headers)
                else:
                    headers.update(dict(api.headers))
                headers["Accept"] = "image/*"

                r = requests.get(full_url, headers=headers, timeout=5)
                print(
                    f"[THUMB] Status: {r.status_code}, "
                    f"Content-Type: {r.headers.get('Content-Type', 'none')}"
                )

                if r.status_code != 200:
                    print(f"[THUMB] Failed: {r.text[:200]}")
                    return

                content_type = r.headers.get("Content-Type", "")
                if "image" not in content_type:
                    print(f"[THUMB] Not an image: {content_type}")
                    return

                print(f"[THUMB] Got {len(r.content)} bytes")
                GLib.idle_add(MemoRow._set_thumbnail, image_box, placeholder, r.content)
            except Exception as e:
                print(f"[THUMB] Error: {e}")

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _set_thumbnail(image_box, placeholder, data):
        """Set thumbnail from image data"""
        import os
        import tempfile

        fd = None
        path = None
        try:
            # Write to temp file
            fd, path = tempfile.mkstemp(suffix=".png")
            os.write(fd, data)
            os.close(fd)
            fd = None  # Mark as closed

            # Load directly with GdkPixbuf (bypass glycin)
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                path, MemoRow.THUMB_SIZE, MemoRow.THUMB_SIZE, True
            )

            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_size_request(MemoRow.THUMB_SIZE, MemoRow.THUMB_SIZE)
            picture.set_can_shrink(False)
            picture.add_css_class("thumbnail")

            image_box.remove(placeholder)
            image_box.append(picture)
            image_box.set_visible(True)
        except Exception as e:
            print(f"[THUMB] Set error: {e}")
        finally:
            # Clean up temp file in all cases
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.close(fd)
            if path is not None:
                with contextlib.suppress(OSError):
                    os.unlink(path)
