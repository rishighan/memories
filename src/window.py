# window.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk, GLib, Gio
import threading
import requests
from .memos_api import MemosAPI


@Gtk.Template(resource_path='/org/quasars/memories/window.ui')
class MemoriesWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MemoriesWindow'

    main_stack = Gtk.Template.Child()
    url_entry = Gtk.Template.Child()
    token_entry = Gtk.Template.Child()
    connect_button = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    memos_list = Gtk.Template.Child()
    scrolled_window = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Load custom CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_resource('/org/quasars/memories/style.css')
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.url_entry.set_text('https://notes.rishighan.com')
        self.connect_button.connect('clicked', self.on_connect_clicked)

        self.api = None
        self.page_token = None
        self.loading_more = False

        # Connect scroll event for pagination
        adj = self.scrolled_window.get_vadjustment()
        adj.connect('value-changed', self.on_scroll)

    def on_connect_clicked(self, button):
        base_url = self.url_entry.get_text().strip()
        token = self.token_entry.get_text().strip()

        if not base_url or not token:
            self.status_label.set_markup('<span foreground="#e01b24">⚠ Please enter both URL and token</span>')
            return

        self.connect_button.set_sensitive(False)
        self.status_label.set_markup('<span>Connecting...</span>')

        def test_connection():
            api = MemosAPI(base_url, token)
            success, message = api.test_connection()
            if success:
                user_info = api.get_user_info()
                memos_success, memos, page_token = api.get_memos()
                return success, message, user_info, api, memos_success, memos, page_token
            return success, message, None, None, False, [], None

        def on_complete(success, message, user_info, api, memos_success, memos, page_token):
            if success and user_info:
                self.api = api
                self.page_token = page_token

                if memos_success:
                    self.load_memos(memos)
                    self.main_stack.set_visible_child_name('memos')
                else:
                    self.status_label.set_markup('<span foreground="#26a269">✓ Connected!</span>\n<span size="small">But failed to load memos</span>')
            elif success:
                self.status_label.set_markup('<span foreground="#26a269">✓ Connected successfully!</span>')
            else:
                self.status_label.set_markup(f'<span foreground="#e01b24">✗ Connection failed</span>\n<span size="small">{message}</span>')
            self.connect_button.set_sensitive(True)

        def worker():
            result = test_connection()
            GLib.idle_add(lambda: on_complete(*result))

        threading.Thread(target=worker, daemon=True).start()

    def on_scroll(self, adjustment):
        """Load more memos when scrolled to bottom"""
        if self.loading_more or not self.page_token or not self.api:
            return

        # Check if near bottom (within 200px)
        value = adjustment.get_value()
        upper = adjustment.get_upper()
        page_size = adjustment.get_page_size()

        if value + page_size >= upper - 200:
            self.load_more_memos()

    def load_memos(self, memos):
        """Load initial memos into the list"""
        # Clear existing items
        while True:
            row = self.memos_list.get_row_at_index(0)
            if row is None:
                break
            self.memos_list.remove(row)

        # Add memos
        for memo in memos:
            row = self.create_memo_row(memo)
            self.memos_list.append(row)

        print(f"Loaded {len(memos)} initial memos")

    def load_more_memos(self):
        """Load next page of memos"""
        if self.loading_more:
            return

        self.loading_more = True
        print("Loading more memos...")

        def worker():
            success, memos, page_token = self.api.get_memos(page_token=self.page_token)

            def on_complete():
                if success and memos:
                    self.page_token = page_token
                    for memo in memos:
                        row = self.create_memo_row(memo)
                        self.memos_list.append(row)
                    print(f"Loaded {len(memos)} more memos")
                else:
                    print("No more memos to load")
                    self.page_token = None
                self.loading_more = False

            GLib.idle_add(on_complete)

        threading.Thread(target=worker, daemon=True).start()

    def create_memo_row(self, memo):
        """Create a row for a memo with custom two-column layout"""
        # Create a list box row container
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
        image_box.set_visible(False)  # Hidden until we have an image

        # Placeholder - will be replaced if image exists
        placeholder = Gtk.Box()
        placeholder.set_size_request(160, 160)
        image_box.append(placeholder)

        main_box.append(image_box)

        # Right column: Text content
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        text_box.set_hexpand(True)
        text_box.set_valign(Gtk.Align.CENTER)

        # Get memo content and limit to 250 chars
        content = memo.get('content', '[No content]')
        if len(content) > 250:
            preview = content[:250] + '...'
        else:
            preview = content if content.strip() else '[Empty memo]'

        # Content label
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

        # Add chevron on the right
        chevron = Gtk.Image.new_from_icon_name('go-next-symbolic')
        chevron.set_valign(Gtk.Align.CENTER)
        main_box.append(chevron)

        list_row.set_child(main_box)

        # Fetch attachments in background
        memo_name = memo.get('name', '')
        if memo_name:
            self.fetch_attachments_for_row(list_row, image_box, placeholder, memo_name)

        return list_row

    def fetch_attachments_for_row(self, list_row, image_box, placeholder, memo_name):
        """Fetch attachments and replace placeholder with image if any exist"""
        def worker():
            attachments = self.api.get_memo_attachments(memo_name)

            if attachments and len(attachments) > 0:
                # Get first attachment
                first_attachment = attachments[0]
                attachment_type = first_attachment.get('type', '')
                attachment_name = first_attachment.get('name', '')
                filename = first_attachment.get('filename', '')

                def on_main_thread():
                    if 'image' in attachment_type.lower() and attachment_name and filename:
                        image_url = f"/file/{attachment_name}/{filename}"
                        self.load_thumbnail(image_box, placeholder, image_url)

                GLib.idle_add(on_main_thread)

        threading.Thread(target=worker, daemon=True).start()

    def load_thumbnail(self, image_box, placeholder, image_url):
        """Load thumbnail image in background"""
        def worker():
            try:
                if image_url.startswith('/'):
                    full_url = f"{self.api.base_url}{image_url}"
                else:
                    full_url = image_url

                headers = self.api.headers.copy()
                headers['Accept'] = 'image/jpeg, image/png, image/*'

                response = requests.get(
                    full_url,
                    headers=headers,
                    timeout=5
                )

                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'image' in content_type or 'jpeg' in content_type or 'png' in content_type:
                        image_data = response.content
                        GLib.idle_add(lambda: self.set_thumbnail(image_box, placeholder, image_data))
            except Exception as e:
                print(f"Error loading thumbnail: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def set_thumbnail(self, image_box, placeholder, image_data):
        """Set thumbnail on main thread"""
        try:
            from gi.repository import GdkPixbuf

            # Load image data
            loader = GdkPixbuf.PixbufLoader()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()

            # Get original dimensions
            width = pixbuf.get_width()
            height = pixbuf.get_height()

            # Crop to square (center crop)
            size = min(width, height)
            x_offset = (width - size) // 2
            y_offset = (height - size) // 2

            cropped = GdkPixbuf.Pixbuf.new_subpixbuf(pixbuf, x_offset, y_offset, size, size)

            # Scale to 160x160
            thumbnail = cropped.scale_simple(160, 160, GdkPixbuf.InterpType.BILINEAR)

            # Create Picture widget (supports border-radius)
            from gi.repository import Gdk
            texture = Gdk.Texture.new_for_pixbuf(thumbnail)
            picture = Gtk.Picture.new_for_paintable(texture)
            picture.set_size_request(160, 160)
            picture.set_can_shrink(False)
            picture.add_css_class('thumbnail')

            # Remove placeholder and add image
            image_box.remove(placeholder)
            image_box.append(picture)

            # Show the image box now that we have an image
            image_box.set_visible(True)
        except Exception as e:
            print(f"Error creating thumbnail: {e}")
