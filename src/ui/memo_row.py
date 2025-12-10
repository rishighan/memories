# memo_row.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk, GLib, Gdk, GdkPixbuf
import threading
import requests


class MemoRow:
    """Handles creation and management of memo list rows"""

    @staticmethod
    def create(memo, api, fetch_attachments_callback):
        """Create a row for a memo with custom two-column layout"""
        list_row = Gtk.ListBoxRow()
        list_row.set_activatable(True)

        # Main horizontal box
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)

        # Left column: Image placeholder (160x160) - hidden by default
        image_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        image_box.set_size_request(160, 160)
        image_box.set_valign(Gtk.Align.START)
        image_box.set_visible(False)

        placeholder = Gtk.Box()
        placeholder.set_size_request(160, 160)
        image_box.append(placeholder)

        main_box.append(image_box)

        # Right column: Text content
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)

        # Content
        content = memo.get('content', '[No content]')
        if len(content) > 250:
            preview = content[:250] + '...'
        else:
            preview = content if content.strip() else '[Empty memo]'

        content_label = Gtk.Label(label=preview)
        content_label.set_wrap(True)
        content_label.set_xalign(0)
        content_label.set_halign(Gtk.Align.START)
        content_label.add_css_class('body')
        text_box.append(content_label)

        # Timestamp
        created_ts = memo.get('createTime', '')
        if created_ts:
            import datetime
            try:
                dt = datetime.datetime.fromisoformat(created_ts.replace('Z', '+00:00'))
                time_label = Gtk.Label(label=dt.strftime('%B %d, %Y at %I:%M %p'))
                time_label.set_xalign(0)
                time_label.set_halign(Gtk.Align.START)
                time_label.add_css_class('dim-label')
                time_label.add_css_class('caption')
                text_box.append(time_label)
            except:
                pass

        main_box.append(text_box)

        # Chevron
        chevron = Gtk.Image.new_from_icon_name('go-next-symbolic')
        chevron.set_valign(Gtk.Align.CENTER)
        main_box.append(chevron)

        list_row.set_child(main_box)

        # Fetch attachments
        memo_name = memo.get('name', '')
        if memo_name:
            fetch_attachments_callback(image_box, placeholder, memo_name, api)

        return list_row

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
