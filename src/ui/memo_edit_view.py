# ui/memo_edit_view.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk, GLib, Pango, Gio, Gdk
import re


class MemoEditView:
    """Combined view for creating and editing memos"""

    def __init__(self, container, title_widget):
        self.container = container
        self.title_widget = title_widget

        self.current_memo = None
        self.attachments = []
        self.existing_attachments = []
        self.MAX_FILE_SIZE = 30 * 1024 * 1024

        self.on_save_callback = None
        self.on_delete_callback = None

        self._update_timeout = None
        self._ui_initialized = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup the editor UI"""
        if self._ui_initialized:
            return

        # Clear container
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

        # Text view for editing
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_left_margin(20)
        self.text_view.set_right_margin(20)
        self.text_view.set_top_margin(60)  # Space for toolbar
        self.text_view.set_bottom_margin(20)

        self.buffer = self.text_view.get_buffer()
        self._create_tags()

        self.buffer.connect('changed', self._on_text_changed)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self._on_key_pressed)
        self.text_view.add_controller(key_controller)

        # Scrolled window for editor
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.text_view)

        # Bottom sheet
        self.bottom_sheet = Adw.BottomSheet()
        self.bottom_sheet.set_content(scrolled)
        self.bottom_sheet.set_sheet(self._create_attachments_content())
        self.bottom_sheet.set_open(False)
        self.bottom_sheet.set_show_drag_handle(True)

        # Overlay for floating toolbar on TOP
        overlay = Gtk.Overlay()
        overlay.set_child(self.bottom_sheet)

        # Floating toolbar
        self.floating_toolbar = self._create_floating_toolbar()
        self.floating_toolbar.set_halign(Gtk.Align.CENTER)
        self.floating_toolbar.set_valign(Gtk.Align.START)
        self.floating_toolbar.set_margin_top(12)
        overlay.add_overlay(self.floating_toolbar)

        self.container.append(overlay)

        self._ui_initialized = True

    def _create_attachments_content(self):
        """Create just the attachments content"""
        sheet_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sheet_box.set_margin_top(12)
        sheet_box.set_margin_bottom(20)
        sheet_box.set_margin_start(20)
        sheet_box.set_margin_end(20)
        sheet_box.set_vexpand(True)

        # Header
        header_label = Gtk.Label(label="Attachments")
        header_label.set_xalign(0)
        header_label.add_css_class("title-3")
        sheet_box.append(header_label)

        # Drop zone
        self.drop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.drop_box.add_css_class("card")
        self.drop_box.set_margin_top(12)
        self.drop_box.set_margin_bottom(12)

        self.drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        self.drop_target.connect('drop', self._on_file_dropped)
        self.drop_box.add_controller(self.drop_target)

        top_spacer = Gtk.Box()
        top_spacer.set_size_request(-1, 16)
        self.drop_box.append(top_spacer)

        icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")
        self.drop_box.append(icon)

        drop_label = Gtk.Label(label="Drop files here or")
        drop_label.add_css_class("dim-label")
        self.drop_box.append(drop_label)

        browse_button = Gtk.Button(label="Browse Files")
        browse_button.set_halign(Gtk.Align.CENTER)
        browse_button.connect('clicked', self._on_browse_clicked)
        self.drop_box.append(browse_button)

        size_label = Gtk.Label(label="Max 30MB per file")
        size_label.add_css_class("caption")
        size_label.add_css_class("dim-label")
        self.drop_box.append(size_label)

        bottom_spacer = Gtk.Box()
        bottom_spacer.set_size_request(-1, 16)
        self.drop_box.append(bottom_spacer)

        sheet_box.append(self.drop_box)

        # Attachments list
        self.attachments_list = Gtk.ListBox()
        self.attachments_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.attachments_list.add_css_class("boxed-list")

        self.attachments_scrolled = Gtk.ScrolledWindow()
        self.attachments_scrolled.set_vexpand(True)
        self.attachments_scrolled.set_min_content_height(150)
        self.attachments_scrolled.set_child(self.attachments_list)
        self.attachments_scrolled.set_visible(False)
        sheet_box.append(self.attachments_scrolled)

        return sheet_box

    def _create_floating_toolbar(self):
        """Create the floating bottom toolbar"""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.add_css_class("card")
        toolbar.add_css_class("toolbar")

        # Attachment button with badge
        self.attach_button = Gtk.Button()
        self.attach_button.add_css_class("flat")
        self.attach_button.set_tooltip_text("Attachments")
        self.attach_button.connect('clicked', self._on_attach_clicked)

        self.attach_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        attach_icon = Gtk.Image.new_from_icon_name("mail-attachment-symbolic")
        self.attach_box.append(attach_icon)

        self.saved_badge = Gtk.Label()
        self.saved_badge.add_css_class("caption")
        self.saved_badge.add_css_class("dim-label")
        self.saved_badge.set_visible(False)
        self.attach_box.append(self.saved_badge)

        self.new_badge = Gtk.Label()
        self.new_badge.add_css_class("caption")
        self.new_badge.add_css_class("success")
        self.new_badge.add_css_class("heading")
        self.new_badge.set_visible(False)
        self.attach_box.append(self.new_badge)

        self.attach_button.set_child(self.attach_box)
        toolbar.append(self.attach_button)

        # Separator
        sep1 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        toolbar.append(sep1)

        # Save/Update button
        self.save_button = Gtk.Button()
        self.save_button.add_css_class("flat")
        self.save_icon = Gtk.Image.new_from_icon_name("document-save-symbolic")
        self.save_button.set_child(self.save_icon)
        self.save_button.set_tooltip_text("Save memo")
        self.save_button.connect('clicked', self._on_save_clicked)
        toolbar.append(self.save_button)

        # Spinner
        self.save_spinner = Gtk.Spinner()
        self.save_spinner.set_visible(False)
        toolbar.append(self.save_spinner)

        # Delete button
        self.delete_button = Gtk.Button()
        self.delete_button.add_css_class("flat")
        delete_icon = Gtk.Image.new_from_icon_name("user-trash-symbolic")
        self.delete_button.set_child(delete_icon)
        self.delete_button.set_tooltip_text("Delete memo")
        self.delete_button.set_visible(False)
        self.delete_button.connect('clicked', self._on_delete_clicked)
        toolbar.append(self.delete_button)

        return toolbar

    def _update_attachment_badges(self):
        """Update attachment count badges"""
        saved_count = len(self.existing_attachments)
        new_count = len(self.attachments)

        if saved_count > 0:
            self.saved_badge.set_label(str(saved_count))
            self.saved_badge.set_visible(True)
        else:
            self.saved_badge.set_visible(False)

        if new_count > 0:
            self.new_badge.set_label(f"+{new_count}")
            self.new_badge.set_visible(True)
        else:
            self.new_badge.set_visible(False)

    def _create_sheet_content(self):
        """Create the bottom sheet content for attachments"""
        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        wrapper.set_size_request(-1, 400)

        sheet_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        sheet_box.set_margin_top(20)
        sheet_box.set_margin_bottom(20)
        sheet_box.set_margin_start(20)
        sheet_box.set_margin_end(20)

        # Header
        header_label = Gtk.Label(label="Attachments")
        header_label.set_xalign(0)
        header_label.add_css_class("title-3")
        sheet_box.append(header_label)

        # Drop zone
        self.drop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.drop_box.add_css_class("card")
        self.drop_box.set_margin_top(20)
        self.drop_box.set_margin_bottom(20)

        self.drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        self.drop_target.connect('drop', self._on_file_dropped)
        self.drop_box.add_controller(self.drop_target)

        top_spacer = Gtk.Box()
        top_spacer.set_size_request(-1, 16)
        self.drop_box.append(top_spacer)

        icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")
        self.drop_box.append(icon)

        drop_label = Gtk.Label(label="Drop files here or")
        drop_label.add_css_class("dim-label")
        self.drop_box.append(drop_label)

        browse_button = Gtk.Button(label="Browse Files")
        browse_button.set_halign(Gtk.Align.CENTER)
        browse_button.connect('clicked', self._on_browse_clicked)
        self.drop_box.append(browse_button)

        size_label = Gtk.Label(label="Max 30MB per file")
        size_label.add_css_class("caption")
        size_label.add_css_class("dim-label")
        self.drop_box.append(size_label)

        bottom_spacer = Gtk.Box()
        bottom_spacer.set_size_request(-1, 16)
        self.drop_box.append(bottom_spacer)

        sheet_box.append(self.drop_box)

        # Attachments list
        self.attachments_list = Gtk.ListBox()
        self.attachments_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.attachments_list.add_css_class("boxed-list")

        self.attachments_scrolled = Gtk.ScrolledWindow()
        self.attachments_scrolled.set_vexpand(True)
        self.attachments_scrolled.set_min_content_height(150)
        self.attachments_scrolled.set_child(self.attachments_list)
        self.attachments_scrolled.set_visible(False)
        sheet_box.append(self.attachments_scrolled)

        wrapper.append(sheet_box)
        return wrapper

    def _on_attach_clicked(self, button):
        """Toggle bottom sheet"""
        is_open = self.bottom_sheet.get_open()
        self.bottom_sheet.set_open(not is_open)

    def _on_file_dropped(self, drop_target, value, x, y):
        """Handle dropped files"""
        if isinstance(value, Gio.File):
            self._add_attachment(value)
            return True
        return False

    def load_memo(self, memo=None):
        """Load a memo for editing or create new"""
        self.current_memo = memo
        self.attachments = []
        self.existing_attachments = []

        # Clear attachments list
        child = self.attachments_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.attachments_list.remove(child)
            child = next_child

        if memo:
            self.save_icon.set_from_icon_name("document-save-as-symbolic")
            self.title_widget.set_title("Edit Memo")
            self.delete_button.set_visible(True)
            self.save_button.set_tooltip_text("Update memo")

            content = memo.get('content', '')
            self.buffer.set_text(content)

            # Load existing attachments
            attachments = memo.get('resources', [])
            if not attachments:
                attachments = memo.get('attachments', [])

            for attach in attachments:
                self.existing_attachments.append(attach)
                row = self._create_existing_attachment_row(attach)
                self.attachments_list.append(row)

            self._update_attachments_visibility()
        else:
            self.save_icon.set_from_icon_name("document-save-symbolic")
            self.title_widget.set_title("New Memo")
            self.delete_button.set_visible(False)
            self.save_button.set_tooltip_text("Save memo")
            self.buffer.set_text('')
            self.attachments_scrolled.set_visible(False)

        self._update_attachment_badges()

        # Close sheet and show toolbar
        self.bottom_sheet.set_open(False)
        self.floating_toolbar.set_visible(True)

    def _update_attachments_visibility(self):
        """Show/hide attachments list based on count"""
        total = len(self.attachments) + len(self.existing_attachments)
        self.attachments_scrolled.set_visible(total > 0)

    def _create_existing_attachment_row(self, attachment):
        """Create a row for an existing attachment"""
        row = Gtk.ListBoxRow()

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        attach_type = attachment.get('type', '')
        if 'image' in attach_type.lower():
            icon = Gtk.Image.new_from_icon_name("image-x-generic-symbolic")
        else:
            icon = Gtk.Image.new_from_icon_name("text-x-generic-symbolic")
        box.append(icon)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)

        filename = attachment.get('filename', 'Unknown')
        name_label = Gtk.Label(label=filename)
        name_label.set_xalign(0)
        name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        info_box.append(name_label)

        size = attachment.get('size', 0)
        if isinstance(size, str):
            size = int(size)
        size_label = Gtk.Label(label=f"{size / 1024:.1f} KB")
        size_label.set_xalign(0)
        size_label.add_css_class("caption")
        size_label.add_css_class("dim-label")
        info_box.append(size_label)

        box.append(info_box)

        badge = Gtk.Label(label="Saved")
        badge.add_css_class("caption")
        badge.add_css_class("dim-label")
        box.append(badge)

        row.set_child(box)
        return row

    def _create_attachment_row(self, attachment):
        """Create a row for a new attachment"""
        row = Gtk.ListBoxRow()

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name("text-x-generic-symbolic")
        box.append(icon)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)

        name_label = Gtk.Label(label=attachment['name'])
        name_label.set_xalign(0)
        name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        info_box.append(name_label)

        size_label = Gtk.Label(label=f"{attachment['size'] / 1024:.1f} KB")
        size_label.set_xalign(0)
        size_label.add_css_class("caption")
        size_label.add_css_class("dim-label")
        info_box.append(size_label)

        box.append(info_box)

        badge = Gtk.Label(label="New")
        badge.add_css_class("caption")
        badge.add_css_class("success")
        box.append(badge)

        remove_button = Gtk.Button(icon_name="user-trash-symbolic")
        remove_button.add_css_class("flat")
        remove_button.connect('clicked', lambda b: self._remove_attachment(attachment, row))
        box.append(remove_button)

        row.set_child(box)
        return row

    def _on_browse_clicked(self, button):
        """Open file chooser"""
        parent_window = self.container.get_root()

        dialog = Gtk.FileChooserNative.new(
            "Choose files to attach",
            parent_window,
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel"
        )
        dialog.set_select_multiple(True)
        dialog.connect('response', self._on_file_chooser_response)
        dialog.show()

    def _on_file_chooser_response(self, dialog, response):
        """Handle file chooser response"""
        if response == Gtk.ResponseType.ACCEPT:
            files = dialog.get_files()
            for i in range(files.get_n_items()):
                file = files.get_item(i)
                self._add_attachment(file)
        dialog.destroy()

    def _add_attachment(self, file):
        """Add a file to attachments"""
        file_info = file.query_info(
            "standard::*",
            Gio.FileQueryInfoFlags.NONE,
            None
        )

        file_size = file_info.get_size()
        file_name = file_info.get_name()

        if file_size > self.MAX_FILE_SIZE:
            print(f"File {file_name} too large")
            return

        for attach in self.attachments:
            if attach['file'].get_path() == file.get_path():
                return

        attachment = {
            'file': file,
            'name': file_name,
            'size': file_size
        }
        self.attachments.append(attachment)

        row = self._create_attachment_row(attachment)
        self.attachments_list.append(row)
        self._update_attachments_visibility()
        self._update_attachment_badges()

    def _remove_attachment(self, attachment, row):
        """Remove an attachment"""
        self.attachments.remove(attachment)
        self.attachments_list.remove(row)
        self._update_attachments_visibility()
        self._update_attachment_badges()

    def _on_save_clicked(self, button):
        """Handle save"""
        text = self.buffer.get_text(
            self.buffer.get_start_iter(),
            self.buffer.get_end_iter(),
            False
        )

        if self.on_save_callback:
            self.on_save_callback(self.current_memo, text, self.attachments)

    def _on_delete_clicked(self, button):
        """Handle delete"""
        if self.current_memo and self.on_delete_callback:
            self.on_delete_callback(self.current_memo)

    def show_saving(self):
        """Show saving state"""
        self.save_button.set_sensitive(False)
        self.save_spinner.set_visible(True)
        self.save_spinner.start()

    def hide_saving(self):
        """Hide saving state"""
        self.save_button.set_sensitive(True)
        self.save_spinner.stop()
        self.save_spinner.set_visible(False)

    def _create_tags(self):
        """Create text tags for markdown styling"""
        tag_table = self.buffer.get_tag_table()

        h1_tag = Gtk.TextTag(name="h1")
        h1_tag.set_property("scale", 2.0)
        h1_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(h1_tag)

        h2_tag = Gtk.TextTag(name="h2")
        h2_tag.set_property("scale", 1.5)
        h2_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(h2_tag)

        h3_tag = Gtk.TextTag(name="h3")
        h3_tag.set_property("scale", 1.25)
        h3_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(h3_tag)

        bold_tag = Gtk.TextTag(name="bold")
        bold_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(bold_tag)

        italic_tag = Gtk.TextTag(name="italic")
        italic_tag.set_property("style", Pango.Style.ITALIC)
        tag_table.add(italic_tag)

        code_tag = Gtk.TextTag(name="code")
        code_tag.set_property("family", "monospace")
        code_tag.set_property("background", "#f4f4f4")
        code_tag.set_property("foreground", "#c7254e")
        tag_table.add(code_tag)

        code_block_tag = Gtk.TextTag(name="code_block")
        code_block_tag.set_property("family", "monospace")
        code_block_tag.set_property("background", "#f6f8fa")
        code_block_tag.set_property("paragraph-background", "#f6f8fa")
        tag_table.add(code_block_tag)

        quote_tag = Gtk.TextTag(name="quote")
        quote_tag.set_property("foreground", "#666")
        quote_tag.set_property("style", Pango.Style.ITALIC)
        quote_tag.set_property("left-margin", 20)
        tag_table.add(quote_tag)

        link_tag = Gtk.TextTag(name="link")
        link_tag.set_property("foreground", "#0366d6")
        link_tag.set_property("underline", Pango.Underline.SINGLE)
        tag_table.add(link_tag)

        strike_tag = Gtk.TextTag(name="strikethrough")
        strike_tag.set_property("strikethrough", True)
        tag_table.add(strike_tag)

        bullet_tag = Gtk.TextTag(name="list_bullet")
        bullet_tag.set_property("foreground", "#0366d6")
        bullet_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(bullet_tag)

        number_tag = Gtk.TextTag(name="list_number")
        number_tag.set_property("foreground", "#0366d6")
        number_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(number_tag)

        list_tag = Gtk.TextTag(name="list_item")
        list_tag.set_property("left-margin", 40)
        list_tag.set_property("indent", -15)
        tag_table.add(list_tag)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses for auto-list continuation"""
        if keyval == Gdk.KEY_Return:
            cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
            line_start = cursor.copy()
            line_start.set_line_offset(0)
            line_text = self.buffer.get_text(line_start, cursor, False)

            ordered_match = re.match(r'^(\s*)(\d+)\.\s+(.*)$', line_text)
            if ordered_match:
                indent = ordered_match.group(1)
                current_num = int(ordered_match.group(2))
                content = ordered_match.group(3)

                if content.strip():
                    next_num = current_num + 1
                    self.buffer.insert_at_cursor(f"\n{indent}{next_num}. ")
                    return True
                else:
                    self.buffer.delete(line_start, cursor)
                    return False

            unordered_match = re.match(r'^(\s*)([-*+])\s+(.*)$', line_text)
            if unordered_match:
                indent = unordered_match.group(1)
                marker = unordered_match.group(2)
                content = unordered_match.group(3)

                if content.strip():
                    self.buffer.insert_at_cursor(f"\n{indent}{marker} ")
                    return True
                else:
                    self.buffer.delete(line_start, cursor)
                    return False

        return False

    def _on_text_changed(self, buffer):
        """Handle text changes with debouncing"""
        if self._update_timeout:
            GLib.source_remove(self._update_timeout)
        self._update_timeout = GLib.timeout_add(150, self._apply_markdown_styling)

    def _apply_markdown_styling(self):
        """Apply markdown styling to the buffer"""
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        self.buffer.remove_all_tags(start, end)

        text = self.buffer.get_text(start, end, False)
        lines = text.split('\n')
        char_offset = 0

        for line in lines:
            line_length = len(line)

            if line.startswith('# '):
                self._apply_tag('h1', char_offset, char_offset + line_length)
            elif line.startswith('## '):
                self._apply_tag('h2', char_offset, char_offset + line_length)
            elif line.startswith('### '):
                self._apply_tag('h3', char_offset, char_offset + line_length)
            elif line.startswith('> '):
                self._apply_tag('quote', char_offset, char_offset + line_length)
            elif line.startswith('    ') or line.startswith('\t'):
                self._apply_tag('code_block', char_offset, char_offset + line_length)
            elif re.match(r'^[\s]*\d+\.\s+', line):
                match = re.match(r'^([\s]*\d+\.\s+)', line)
                if match:
                    number_end = char_offset + len(match.group(1))
                    self._apply_tag('list_number', char_offset, number_end)
                    self._apply_tag('list_item', char_offset, char_offset + line_length)
            elif re.match(r'^[\s]*[-*+]\s+', line):
                match = re.match(r'^([\s]*[-*+]\s+)', line)
                if match:
                    bullet_end = char_offset + len(match.group(1))
                    self._apply_tag('list_bullet', char_offset, bullet_end)
                    self._apply_tag('list_item', char_offset, char_offset + line_length)

            if not line.startswith(('# ', '## ', '### ', '> ', '    ', '\t')):
                for match in re.finditer(r'\*\*(.+?)\*\*', line):
                    self._apply_tag('bold', char_offset + match.start(), char_offset + match.end())
                for match in re.finditer(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', line):
                    self._apply_tag('italic', char_offset + match.start(), char_offset + match.end())
                for match in re.finditer(r'_(.+?)_', line):
                    self._apply_tag('italic', char_offset + match.start(), char_offset + match.end())
                for match in re.finditer(r'`(.+?)`', line):
                    self._apply_tag('code', char_offset + match.start(), char_offset + match.end())
                for match in re.finditer(r'~~(.+?)~~', line):
                    self._apply_tag('strikethrough', char_offset + match.start(), char_offset + match.end())
                for match in re.finditer(r'\[(.+?)\]\((.+?)\)', line):
                    self._apply_tag('link', char_offset + match.start(), char_offset + match.end())

            char_offset += line_length + 1

        self._update_timeout = None
        return False

    def _apply_tag(self, tag_name, start_offset, end_offset):
        """Apply a tag to a range of text"""
        start_iter = self.buffer.get_iter_at_offset(start_offset)
        end_iter = self.buffer.get_iter_at_offset(end_offset)
        self.buffer.apply_tag_by_name(tag_name, start_iter, end_iter)
