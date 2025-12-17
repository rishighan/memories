# ui/memo_detail_view.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk, Adw, Pango, GLib
from datetime import datetime


class MemoDetailView:
    """Handles displaying a single memo's details"""

    def __init__(self, container, api):
        self.container = container
        self.api = api
        self.current_memo = None

    def show_memo(self, memo):
        """Display memo details"""
        self.current_memo = memo

        # Clear container
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

        # Metadata section
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        meta_box.set_margin_bottom(16)

        # Date
        create_time = memo.get('createTime', '')
        if create_time:
            try:
                dt = datetime.fromisoformat(create_time.replace('Z', '+00:00'))
                date_str = dt.strftime('%B %d, %Y at %I:%M %p')
            except:
                date_str = create_time
        else:
            date_str = 'Unknown date'

        date_label = Gtk.Label(label=date_str)
        date_label.add_css_class('dim-label')
        date_label.add_css_class('caption')
        date_label.set_xalign(0)
        meta_box.append(date_label)

        # Visibility
        visibility = memo.get('visibility', 'PRIVATE')
        visibility_icon = Gtk.Image.new_from_icon_name(
            'security-high-symbolic' if visibility == 'PRIVATE' else 'security-medium-symbolic'
        )
        visibility_icon.add_css_class('dim-label')
        meta_box.append(visibility_icon)

        self.container.append(meta_box)

        # Content
        content = memo.get('content', '')

        content_label = Gtk.Label(label=content)
        content_label.set_xalign(0)
        content_label.set_wrap(True)
        content_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        content_label.set_selectable(True)
        content_label.add_css_class('body')
        self.container.append(content_label)

        # Attachments section
        attachments = memo.get('resources', [])
        if not attachments:
            attachments = memo.get('attachments', [])

        if attachments:
            # Separator
            separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            separator.set_margin_top(16)
            separator.set_margin_bottom(16)
            self.container.append(separator)

            # Attachments header
            attach_header = Gtk.Label(label=f"Attachments ({len(attachments)})")
            attach_header.set_xalign(0)
            attach_header.add_css_class('title-4')
            attach_header.set_margin_bottom(12)
            self.container.append(attach_header)

            # Attachments grid
            attachments_flow = Gtk.FlowBox()
            attachments_flow.set_selection_mode(Gtk.SelectionMode.NONE)
            attachments_flow.set_max_children_per_line(3)
            attachments_flow.set_column_spacing(12)
            attachments_flow.set_row_spacing(12)

            for attachment in attachments:
                attach_widget = self._create_attachment_widget(attachment)
                attachments_flow.append(attach_widget)

            self.container.append(attachments_flow)

        # Tags section
        tags = memo.get('tags', [])
        if tags:
            separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            separator.set_margin_top(16)
            separator.set_margin_bottom(16)
            self.container.append(separator)

            tags_box = Gtk.FlowBox()
            tags_box.set_selection_mode(Gtk.SelectionMode.NONE)
            tags_box.set_max_children_per_line(10)
            tags_box.set_column_spacing(8)
            tags_box.set_row_spacing(8)

            for tag in tags:
                tag_label = Gtk.Label(label=f"#{tag}")
                tag_label.add_css_class('caption')
                tag_label.set_margin_start(8)
                tag_label.set_margin_end(8)
                tag_label.set_margin_top(4)
                tag_label.set_margin_bottom(4)

                tag_box = Gtk.Box()
                tag_box.append(tag_label)
                tag_box.add_css_class('card')

                tags_box.append(tag_box)

            self.container.append(tags_box)

    def _create_attachment_widget(self, attachment):
        """Create a widget for an attachment"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class('card')
        box.set_size_request(200, -1)

        attachment_type = attachment.get('type', '')
        attachment_name = attachment.get('name', '')
        filename = attachment.get('filename', 'Unknown')

        # Image preview for images
        if 'image' in attachment_type.lower():
            image = Gtk.Picture()
            image.set_size_request(200, 150)
            image.set_can_shrink(True)
            image.add_css_class('thumbnail')

            # Load image
            if attachment_name and filename:
                image_url = f"{self.api.base_url}/file/{attachment_name}/{filename}"
                self._load_image_async(image, image_url)

            box.append(image)
        else:
            # File icon for non-images
            icon = Gtk.Image.new_from_icon_name('text-x-generic-symbolic')
            icon.set_pixel_size(48)
            icon.set_margin_top(16)
            icon.set_margin_bottom(16)
            box.append(icon)

        # Filename
        name_label = Gtk.Label(label=filename)
        name_label.set_xalign(0)
        name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        name_label.set_margin_start(12)
        name_label.set_margin_end(12)
        name_label.set_margin_bottom(12)
        name_label.add_css_class('caption')
        box.append(name_label)

        return box

    def _load_image_async(self, image, url):
        """Load image asynchronously"""
        import threading

        def worker():
            try:
                import requests
                response = requests.get(
                    url,
                    headers=self.api.headers,
                    timeout=10
                )

                if response.status_code == 200:
                    def on_complete():
                        try:
                            from gi.repository import GdkPixbuf, Gio

                            loader = GdkPixbuf.PixbufLoader()
                            loader.write(response.content)
                            loader.close()

                            pixbuf = loader.get_pixbuf()
                            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                            image.set_paintable(texture)
                        except Exception as e:
                            print(f"Error setting image: {e}")

                    GLib.idle_add(on_complete)
            except Exception as e:
                print(f"Error loading image: {e}")

        threading.Thread(target=worker, daemon=True).start()
