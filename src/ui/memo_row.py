# memo_row.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Pango
import threading
import requests


class MemoRow:
    """Handles creation and management of memo list rows"""

    @staticmethod
    def create(memo, api, fetch_attachments_callback):
        """Create a memo row"""
        row = Gtk.ListBoxRow()
        row.set_activatable(True)

        # Store memo data on the row for retrieval
        row.memo_data = memo

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Check for attachments
        attachments = memo.get('resources', [])
        if not attachments:
            attachments = memo.get('attachments', [])

        image_attachments = [a for a in attachments if a.get('type', '').startswith('image/')]

        # Show thumbnail with stack effect for multiple images
        if image_attachments:
            if len(image_attachments) > 1:
                # Create overlay for stack effect
                overlay = Gtk.Overlay()

                # Base thumbnail (bottom of stack)
                base_box = Gtk.Box()
                base_box.set_size_request(160, 160)
                base_box.add_css_class("thumbnail")

                base_image = Gtk.Picture()
                base_image.set_size_request(160, 160)
                base_image.set_can_shrink(True)
                base_image.add_css_class("thumbnail")

                base_box.append(base_image)
                overlay.set_child(base_box)

                # Add stacked card indicators (show that there are more)
                for i in range(1, min(3, len(image_attachments))):
                    stack_indicator = Gtk.Box()
                    stack_indicator.set_size_request(150 - (i * 8), 150 - (i * 8))
                    stack_indicator.add_css_class("card")
                    stack_indicator.set_margin_start(5 + (i * 4))
                    stack_indicator.set_margin_top(5 + (i * 4))
                    stack_indicator.set_halign(Gtk.Align.END)
                    stack_indicator.set_valign(Gtk.Align.START)
                    stack_indicator.set_opacity(0.8 - (i * 0.2))

                    overlay.add_overlay(stack_indicator)

                # Badge showing count
                if len(image_attachments) > 1:
                    # Badge container with dark background
                    badge_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                    badge_container.set_halign(Gtk.Align.END)
                    badge_container.set_valign(Gtk.Align.END)
                    badge_container.set_margin_end(8)
                    badge_container.set_margin_bottom(8)

                    badge_label = Gtk.Label(label=f"+{len(image_attachments) - 1}")
                    badge_label.add_css_class("heading")
                    badge_label.set_margin_start(8)
                    badge_label.set_margin_end(8)
                    badge_label.set_margin_top(4)
                    badge_label.set_margin_bottom(4)

                    badge_container.append(badge_label)
                    badge_container.add_css_class("osd")  # Adds dark semi-transparent background

                    overlay.add_overlay(badge_container)

                box.append(overlay)

                # Fetch first image for the base
                memo_name = memo.get('name', '')
                fetch_attachments_callback(base_box, base_image, memo_name, api)

            else:
                # Single image - no stack
                thumbnail_box = Gtk.Box()
                thumbnail_box.set_size_request(160, 160)
                thumbnail_box.add_css_class("thumbnail")

                image = Gtk.Picture()
                image.set_size_request(160, 160)
                image.set_can_shrink(True)
                image.add_css_class("thumbnail")

                thumbnail_box.append(image)
                box.append(thumbnail_box)

                memo_name = memo.get('name', '')
                fetch_attachments_callback(thumbnail_box, image, memo_name, api)

        # Content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        content_box.set_hexpand(True)

        # Memo text
        content = memo.get('content', '')[:200]
        if len(memo.get('content', '')) > 200:
            content += '...'

        text_label = Gtk.Label(label=content)
        text_label.set_xalign(0)
        text_label.set_wrap(True)
        text_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        text_label.set_max_width_chars(50)
        content_box.append(text_label)

        # Date
        create_time = memo.get('createTime', '')
        if create_time:
            from datetime import datetime
            dt = datetime.fromisoformat(create_time.replace('Z', '+00:00'))
            date_str = dt.strftime('%B %d, %Y at %I:%M %p')

            date_label = Gtk.Label(label=date_str)
            date_label.set_xalign(0)
            date_label.add_css_class('caption')
            date_label.add_css_class('dim-label')
            content_box.append(date_label)

        box.append(content_box)

        # Arrow
        arrow = Gtk.Image.new_from_icon_name('go-next-symbolic')
        arrow.set_valign(Gtk.Align.CENTER)
        box.append(arrow)

        row.set_child(box)
        return row

    @staticmethod
    def fetch_attachments(image_box, placeholder, memo_name, api):
        """Fetch attachments and replace placeholder with image"""
        def worker():
            attachments = api.get_memo_attachments(memo_name)

            if attachments and len(attachments) > 0:
                first_attachment = attachments[0]
                attachment_type = first_attachment.get('type', '')
                attachment_name = first_attachment.get('name', '')
                filename = first_attachment.get('filename', '')

                def on_main_thread():
                    if 'image' in attachment_type.lower() and attachment_name and filename:
                        image_url = f"/file/{attachment_name}/{filename}"
                        MemoRow.load_thumbnail(image_box, placeholder, image_url, api)

                GLib.idle_add(on_main_thread)

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def load_thumbnail(image_box, placeholder, image_url, api):
        """Load thumbnail image in background"""
        def worker():
            try:
                if image_url.startswith('/'):
                    full_url = f"{api.base_url}{image_url}"
                else:
                    full_url = image_url

                headers = api.headers.copy()
                headers['Accept'] = 'image/jpeg, image/png, image/*'

                response = requests.get(full_url, headers=headers, timeout=5)

                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'image' in content_type or 'jpeg' in content_type or 'png' in content_type:
                        image_data = response.content
                        GLib.idle_add(lambda: MemoRow.set_thumbnail(image_box, placeholder, image_data))
            except Exception as e:
                print(f"Error loading thumbnail: {e}")

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def set_thumbnail(image_box, placeholder, image_data):
        """Set thumbnail on main thread"""
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()

            width = pixbuf.get_width()
            height = pixbuf.get_height()

            # Crop to square
            size = min(width, height)
            x_offset = (width - size) // 2
            y_offset = (height - size) // 2

            cropped = GdkPixbuf.Pixbuf.new_subpixbuf(pixbuf, x_offset, y_offset, size, size)
            thumbnail = cropped.scale_simple(160, 160, GdkPixbuf.InterpType.BILINEAR)

            texture = Gdk.Texture.new_for_pixbuf(thumbnail)
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_size_request(160, 160)
            picture.set_can_shrink(False)
            picture.add_css_class('thumbnail')

            image_box.remove(placeholder)
            image_box.append(picture)
            image_box.set_visible(True)
        except Exception as e:
            print(f"Error creating thumbnail: {e}")

    @staticmethod
    def _create_thumbnail_stack(memo, api, fetch_attachments_callback):
        """Create a stacked thumbnail view for multiple attachments"""
        overlay = Gtk.Overlay()

        # Get attachments
        attachments = memo.get('resources', [])
        if not attachments:
            attachments = memo.get('attachments', [])

        image_attachments = [a for a in attachments if a.get('type', '').startswith('image/')]

        if not image_attachments:
            return None

        # Limit to first 3 images for stack effect
        display_count = min(len(image_attachments), 3)

        # Base image (largest, bottom of stack)
        base_box = Gtk.Box()
        base_box.set_size_request(160, 160)
        base_box.add_css_class("thumbnail")

        base_image = Gtk.Picture()
        base_image.set_size_request(160, 160)
        base_image.set_can_shrink(True)
        base_image.add_css_class("thumbnail")

        base_box.append(base_image)
        overlay.set_child(base_box)

        # Add stacked images on top with offset
        if display_count > 1:
            for i in range(1, display_count):
                offset_box = Gtk.Box()
                offset_box.set_size_request(140 - (i * 10), 140 - (i * 10))
                offset_box.add_css_class("thumbnail")
                offset_box.set_margin_start(10 + (i * 5))
                offset_box.set_margin_top(10 + (i * 5))
                offset_box.set_halign(Gtk.Align.END)
                offset_box.set_valign(Gtk.Align.START)

                # Add semi-transparent background
                offset_box.set_opacity(0.9)

                stacked_image = Gtk.Picture()
                stacked_image.set_size_request(140 - (i * 10), 140 - (i * 10))
                stacked_image.set_can_shrink(True)
                stacked_image.add_css_class("thumbnail")

                offset_box.append(stacked_image)
                overlay.add_overlay(offset_box)

        # If more than 3, show count badge
        if len(image_attachments) > 3:
            badge_box = Gtk.Box()
            badge_box.set_halign(Gtk.Align.END)
            badge_box.set_valign(Gtk.Align.END)
            badge_box.set_margin_end(8)
            badge_box.set_margin_bottom(8)

            badge_label = Gtk.Label(label=f"+{len(image_attachments) - 3}")
            badge_label.add_css_class("caption")
            badge_label.set_margin_start(8)
            badge_label.set_margin_end(8)
            badge_label.set_margin_top(4)
            badge_label.set_margin_bottom(4)

            # Add background to badge
            badge_box.append(badge_label)
            badge_box.add_css_class("card")

            overlay.add_overlay(badge_box)

        # Fetch and load images
        fetch_attachments_callback(memo, api, base_image, image_attachments)

        return overlay
