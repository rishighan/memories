# ui/new_memo_dialog.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk, GLib, Pango, Gio, Gdk
import re


class NewMemoDialog(Adw.Dialog):
    """Dialog for creating a new memo with inline markdown rendering"""

    def __init__(self):
        super().__init__()

        self.set_content_width(700)
        self.set_content_height(700)

        self.attachments = []  # Store selected files
        self.MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB in bytes

        # Create text view for editing
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_left_margin(20)
        self.text_view.set_right_margin(20)
        self.text_view.set_top_margin(20)
        self.text_view.set_bottom_margin(20)

        # Get buffer and create tags for markdown styling
        self.buffer = self.text_view.get_buffer()
        self._create_tags()

        # Connect to buffer changes for live rendering
        self.buffer.connect('changed', self._on_text_changed)

        # Connect key press for auto-list continuation
        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self._on_key_pressed)
        self.text_view.add_controller(key_controller)

        # Scrolled window for editor
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.text_view)

        # Save button
        self.save_button = Gtk.Button(label="Save")
        self.save_button.add_css_class("suggested-action")

        # Spinner for save progress
        self.spinner = Gtk.Spinner()
        self.spinner.set_visible(False)

        # Attach button with badge
        attach_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.attach_button = Gtk.Button()
        self.attach_button.set_child(attach_box)
        self.attach_button.set_tooltip_text("Add attachments")
        self.attach_button.connect('clicked', self._on_attach_clicked)

        attach_icon = Gtk.Image.new_from_icon_name("mail-attachment-symbolic")
        attach_box.append(attach_icon)

        self.attach_badge = Gtk.Label()
        self.attach_badge.add_css_class("caption")
        self.attach_badge.set_visible(False)
        attach_box.append(self.attach_badge)

        # Cancel button
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect('clicked', lambda b: self.close())

        # Header
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="New Memo"))
        header.pack_start(cancel_button)
        header.pack_start(self.attach_button)
        header.pack_end(self.save_button)
        header.pack_end(self.spinner)

        # Toolbar view (main content)
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(scrolled)

        # Create bottom sheet
        self.bottom_sheet = Adw.BottomSheet()
        self.bottom_sheet.set_content(toolbar_view)
        self.bottom_sheet.set_sheet(self._create_sheet_content())
        self.bottom_sheet.set_open(False)

        # Set the bottom sheet as the dialog child
        self.set_child(self.bottom_sheet)

        self.on_save_callback = None
        self.save_button.connect('clicked', self._on_save)

        # Debounce timer
        self._update_timeout = None

    def _create_sheet_content(self):
        """Create the bottom sheet content"""
        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        wrapper.set_size_request(-1, 550)

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
        self.drop_box.set_margin_start(20)
        self.drop_box.set_margin_end(20)

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

        # Attachments list - hidden by default
        self.attachments_list = Gtk.ListBox()
        self.attachments_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.attachments_list.add_css_class("boxed-list")

        self.attachments_scrolled = Gtk.ScrolledWindow()
        self.attachments_scrolled.set_vexpand(False)
        self.attachments_scrolled.set_min_content_height(200)
        self.attachments_scrolled.set_max_content_height(200)
        self.attachments_scrolled.set_propagate_natural_height(True)
        self.attachments_scrolled.set_child(self.attachments_list)
        self.attachments_scrolled.set_visible(False)  # Hidden by default
        sheet_box.append(self.attachments_scrolled)

        wrapper.append(sheet_box)
        return wrapper

    def _on_attach_clicked(self, button):
        """Toggle bottom sheet"""
        is_open = self.bottom_sheet.get_open()

        if not is_open:
            # Add drop target when opening
            if not hasattr(self, 'drop_target') or self.drop_target is None:
                self.drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
                self.drop_target.connect('drop', self._on_file_dropped)
                self.drop_box.add_controller(self.drop_target)

        self.bottom_sheet.set_open(not is_open)

    def _on_browse_clicked(self, button):
        """Open file chooser dialog"""
        dialog = Gtk.FileChooserNative.new(
            "Choose files to attach",
            self,
            Gtk.FileChooserAction.OPEN,
            "Select",
            "Cancel"
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

    def _on_file_dropped(self, drop_target, value, x, y):
        """Handle dropped files"""
        if isinstance(value, Gio.File):
            self._add_attachment(value)
            return True
        return False

    def _add_attachment(self, file):
        """Add a file to attachments list"""
        file_info = file.query_info(
            "standard::*",
            Gio.FileQueryInfoFlags.NONE,
            None
        )

        file_size = file_info.get_size()
        file_name = file_info.get_name()

        # Check file size
        if file_size > self.MAX_FILE_SIZE:
            print(f"File {file_name} too large: {file_size / 1024 / 1024:.1f}MB")
            return

        # Check if already added
        for attachment in self.attachments:
            if attachment['file'].get_path() == file.get_path():
                print(f"File {file_name} already attached")
                return

        # Add to list
        attachment = {
            'file': file,
            'name': file_name,
            'size': file_size
        }
        self.attachments.append(attachment)

        # Create list row
        row = self._create_attachment_row(attachment)
        self.attachments_list.append(row)

        # Update UI
        self._update_attachment_ui()

        print(f"Added attachment: {file_name} ({file_size / 1024:.1f}KB)")

    def _create_attachment_row(self, attachment):
        """Create a row for an attachment"""
        row = Gtk.ListBoxRow()

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # File icon
        icon = Gtk.Image.new_from_icon_name("text-x-generic-symbolic")
        box.append(icon)

        # File info
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

        # Remove button
        remove_button = Gtk.Button(icon_name="user-trash-symbolic")
        remove_button.add_css_class("flat")
        remove_button.connect('clicked', lambda b: self._remove_attachment(attachment, row))
        box.append(remove_button)

        row.set_child(box)
        return row

    def _remove_attachment(self, attachment, row):
        """Remove an attachment"""
        self.attachments.remove(attachment)
        self.attachments_list.remove(row)
        self._update_attachment_ui()
        print(f"Removed attachment: {attachment['name']}")

    def _update_attachment_ui(self):
        """Update attachment badge and list visibility"""
        count = len(self.attachments)

        # Update badge
        if count > 0:
            self.attach_badge.set_label(str(count))
            self.attach_badge.set_visible(True)
            # Show list
            self.attachments_scrolled.set_visible(True)
        else:
            self.attach_badge.set_visible(False)
            # Hide list
            self.attachments_scrolled.set_visible(False)

    def _create_tags(self):
        """Create text tags for markdown styling"""
        tag_table = self.buffer.get_tag_table()

        # Heading 1
        h1_tag = Gtk.TextTag(name="h1")
        h1_tag.set_property("scale", 2.0)
        h1_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(h1_tag)

        # Heading 2
        h2_tag = Gtk.TextTag(name="h2")
        h2_tag.set_property("scale", 1.5)
        h2_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(h2_tag)

        # Heading 3
        h3_tag = Gtk.TextTag(name="h3")
        h3_tag.set_property("scale", 1.25)
        h3_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(h3_tag)

        # Bold
        bold_tag = Gtk.TextTag(name="bold")
        bold_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(bold_tag)

        # Italic
        italic_tag = Gtk.TextTag(name="italic")
        italic_tag.set_property("style", Pango.Style.ITALIC)
        tag_table.add(italic_tag)

        # Code inline
        code_tag = Gtk.TextTag(name="code")
        code_tag.set_property("family", "monospace")
        code_tag.set_property("background", "#f4f4f4")
        code_tag.set_property("foreground", "#c7254e")
        tag_table.add(code_tag)

        # Code block
        code_block_tag = Gtk.TextTag(name="code_block")
        code_block_tag.set_property("family", "monospace")
        code_block_tag.set_property("background", "#f6f8fa")
        code_block_tag.set_property("paragraph-background", "#f6f8fa")
        tag_table.add(code_block_tag)

        # Blockquote
        quote_tag = Gtk.TextTag(name="quote")
        quote_tag.set_property("foreground", "#666")
        quote_tag.set_property("style", Pango.Style.ITALIC)
        quote_tag.set_property("left-margin", 20)
        tag_table.add(quote_tag)

        # Link
        link_tag = Gtk.TextTag(name="link")
        link_tag.set_property("foreground", "#0366d6")
        link_tag.set_property("underline", Pango.Underline.SINGLE)
        tag_table.add(link_tag)

        # Strikethrough
        strike_tag = Gtk.TextTag(name="strikethrough")
        strike_tag.set_property("strikethrough", True)
        tag_table.add(strike_tag)

        # List bullet (the marker itself)
        bullet_tag = Gtk.TextTag(name="list_bullet")
        bullet_tag.set_property("foreground", "#0366d6")
        bullet_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(bullet_tag)

        # List number (the 1. 2. etc marker)
        number_tag = Gtk.TextTag(name="list_number")
        number_tag.set_property("foreground", "#0366d6")
        number_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(number_tag)

        # List item (the whole line)
        list_tag = Gtk.TextTag(name="list_item")
        list_tag.set_property("left-margin", 40)
        list_tag.set_property("indent", -15)
        tag_table.add(list_tag)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses for auto-list continuation"""

        if keyval == Gdk.KEY_Return:
            # Get cursor position
            cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())

            # Get current line
            line_start = cursor.copy()
            line_start.set_line_offset(0)
            line_text = self.buffer.get_text(line_start, cursor, False)

            # Check for ordered list
            ordered_match = re.match(r'^(\s*)(\d+)\.\s+(.*)$', line_text)
            if ordered_match:
                indent = ordered_match.group(1)
                current_num = int(ordered_match.group(2))
                content = ordered_match.group(3)

                # If line has content, continue list with next number
                if content.strip():
                    next_num = current_num + 1
                    self.buffer.insert_at_cursor(f"\n{indent}{next_num}. ")
                    return True  # Consume the event
                else:
                    # Empty list item - end the list
                    # Delete the empty list marker
                    self.buffer.delete(line_start, cursor)
                    return False

            # Check for unordered list
            unordered_match = re.match(r'^(\s*)([-*+])\s+(.*)$', line_text)
            if unordered_match:
                indent = unordered_match.group(1)
                marker = unordered_match.group(2)
                content = unordered_match.group(3)

                # If line has content, continue list with same marker
                if content.strip():
                    self.buffer.insert_at_cursor(f"\n{indent}{marker} ")
                    return True  # Consume the event
                else:
                    # Empty list item - end the list
                    # Delete the empty list marker
                    self.buffer.delete(line_start, cursor)
                    return False

        return False  # Don't consume the event

    def _on_text_changed(self, buffer):
        """Handle text changes with debouncing"""
        if self._update_timeout:
            GLib.source_remove(self._update_timeout)

        self._update_timeout = GLib.timeout_add(150, self._apply_markdown_styling)

    def _apply_markdown_styling(self):
        """Apply markdown styling to the buffer"""
        # Remove all existing tags
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        self.buffer.remove_all_tags(start, end)

        # Get all text
        text = self.buffer.get_text(start, end, False)

        # Apply styling based on markdown patterns
        lines = text.split('\n')
        char_offset = 0

        for line in lines:
            line_length = len(line)

            # Headers
            if line.startswith('# '):
                self._apply_tag('h1', char_offset, char_offset + line_length)
            elif line.startswith('## '):
                self._apply_tag('h2', char_offset, char_offset + line_length)
            elif line.startswith('### '):
                self._apply_tag('h3', char_offset, char_offset + line_length)

            # Blockquote
            elif line.startswith('> '):
                self._apply_tag('quote', char_offset, char_offset + line_length)

            # Code block (lines starting with 4 spaces or tab)
            elif line.startswith('    ') or line.startswith('\t'):
                self._apply_tag('code_block', char_offset, char_offset + line_length)

            # Ordered list (1. 2. etc)
            elif re.match(r'^[\s]*\d+\.\s+', line):
                match = re.match(r'^([\s]*\d+\.\s+)', line)
                if match:
                    number_end = char_offset + len(match.group(1))
                    self._apply_tag('list_number', char_offset, number_end)
                    self._apply_tag('list_item', char_offset, char_offset + line_length)

            # Unordered list (-, *, +)
            elif re.match(r'^[\s]*[-*+]\s+', line):
                match = re.match(r'^([\s]*[-*+]\s+)', line)
                if match:
                    bullet_end = char_offset + len(match.group(1))
                    self._apply_tag('list_bullet', char_offset, bullet_end)
                    self._apply_tag('list_item', char_offset, char_offset + line_length)

            # Inline formatting (bold, italic, code, strikethrough, links)
            if not line.startswith(('# ', '## ', '### ', '> ', '    ', '\t')):
                # Bold **text**
                for match in re.finditer(r'\*\*(.+?)\*\*', line):
                    self._apply_tag('bold', char_offset + match.start(), char_offset + match.end())

                # Italic *text* or _text_
                for match in re.finditer(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', line):
                    self._apply_tag('italic', char_offset + match.start(), char_offset + match.end())
                for match in re.finditer(r'_(.+?)_', line):
                    self._apply_tag('italic', char_offset + match.start(), char_offset + match.end())

                # Inline code `code`
                for match in re.finditer(r'`(.+?)`', line):
                    self._apply_tag('code', char_offset + match.start(), char_offset + match.end())

                # Strikethrough ~~text~~
                for match in re.finditer(r'~~(.+?)~~', line):
                    self._apply_tag('strikethrough', char_offset + match.start(), char_offset + match.end())

                # Links [text](url)
                for match in re.finditer(r'\[(.+?)\]\((.+?)\)', line):
                    self._apply_tag('link', char_offset + match.start(), char_offset + match.end())

            # Move to next line (+ 1 for newline character)
            char_offset += line_length + 1

        self._update_timeout = None
        return False

    def _apply_tag(self, tag_name, start_offset, end_offset):
        """Apply a tag to a range of text"""
        start_iter = self.buffer.get_iter_at_offset(start_offset)
        end_iter = self.buffer.get_iter_at_offset(end_offset)
        self.buffer.apply_tag_by_name(tag_name, start_iter, end_iter)

    def _on_save(self, button):
        """Handle save button click"""
        text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)

        if self.on_save_callback:
            self.on_save_callback(text)

        # Clear and close
        self.buffer.set_text('')

    def show_saving(self):
        """Show saving state"""
        self.save_button.set_sensitive(False)
        self.spinner.start()
        self.spinner.set_visible(True)

    def hide_saving(self):
        """Hide saving state"""
        self.save_button.set_sensitive(True)
        self.spinner.stop()
        self.spinner.set_visible(False)

    def clear(self):
        """Clear the text view"""
        self.buffer.set_text('')
        self.attachments.clear()
        # Clear attachments list
        child = self.attachments_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.attachments_list.remove(child)
            child = next_child
