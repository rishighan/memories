# ui/memo_edit_view.py
# Memo editor with floating toolbar and attachment bottom sheet

from gi.repository import Adw, Gtk, GLib, Pango, Gio, Gdk
import re


class MemoEditView:
    """Memo editor: text view + floating toolbar + attachment sheet"""

    def __init__(self, container, title_widget):
        self.container = container
        self.title_widget = title_widget
        self.current_memo = None
        self.attachments = []  # New attachments to upload
        self.existing_attachments = []  # Already saved attachments
        self.MAX_FILE_SIZE = 30 * 1024 * 1024
        self.on_save_callback = None
        self.on_delete_callback = None
        self._update_timeout = None
        self._ui_initialized = False
        self._setup_ui()

    # -------------------------------------------------------------------------
    # UI SETUP
    # -------------------------------------------------------------------------

    def _setup_ui(self):
        """Build the UI: overlay with text editor + floating toolbar"""
        if self._ui_initialized:
            return

        # Clear container
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

        # Text editor
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_left_margin(20)
        self.text_view.set_right_margin(20)
        self.text_view.set_top_margin(80)  # Space for floating toolbar
        self.text_view.set_bottom_margin(20)

        self.buffer = self.text_view.get_buffer()
        self._create_tags()
        self.buffer.connect('changed', self._on_text_changed)

        # Auto-list continuation on Enter
        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self._on_key_pressed)
        self.text_view.add_controller(key_controller)

        # Scrollable text area
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.text_view)

        # Bottom sheet for attachments
        self.bottom_sheet = Adw.BottomSheet()
        self.bottom_sheet.set_content(scrolled)
        self.bottom_sheet.set_sheet(self._create_attachments_sheet())
        self.bottom_sheet.set_open(False)
        self.bottom_sheet.set_show_drag_handle(True)

        # Overlay: bottom sheet + floating toolbar on top
        overlay = Gtk.Overlay()
        overlay.set_child(self.bottom_sheet)

        self.floating_toolbar = self._create_toolbar()
        self.floating_toolbar.set_halign(Gtk.Align.CENTER)
        self.floating_toolbar.set_valign(Gtk.Align.START)
        self.floating_toolbar.set_margin_top(12)
        overlay.add_overlay(self.floating_toolbar)

        self.container.append(overlay)
        self._ui_initialized = True

    def _create_toolbar(self):
        """Floating toolbar: attach, save, delete"""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.add_css_class("card")
        toolbar.add_css_class("toolbar")

        # Attach button + badges
        self.attach_button = Gtk.Button()
        self.attach_button.add_css_class("flat")
        self.attach_button.set_tooltip_text("Attachments")
        self.attach_button.connect('clicked', self._on_attach_clicked)

        self.attach_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.attach_box.append(Gtk.Image.new_from_icon_name("mail-attachment-symbolic"))

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
        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Save button
        self.save_button = Gtk.Button()
        self.save_button.add_css_class("flat")
        self.save_icon = Gtk.Image.new_from_icon_name("document-save-symbolic")
        self.save_button.set_child(self.save_icon)
        self.save_button.set_tooltip_text("Save memo")
        self.save_button.connect('clicked', self._on_save_clicked)
        toolbar.append(self.save_button)

        # Spinner (hidden by default)
        self.save_spinner = Gtk.Spinner()
        self.save_spinner.set_visible(False)
        toolbar.append(self.save_spinner)

        # Delete button (hidden for new memos)
        self.delete_button = Gtk.Button()
        self.delete_button.add_css_class("flat")
        self.delete_button.set_child(Gtk.Image.new_from_icon_name("user-trash-symbolic"))
        self.delete_button.set_tooltip_text("Delete memo")
        self.delete_button.set_visible(False)
        self.delete_button.connect('clicked', self._on_delete_clicked)
        toolbar.append(self.delete_button)

        return toolbar

    def _create_attachments_sheet(self):
        """Bottom sheet content: drop zone + attachment list"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

        # Header
        header = Gtk.Label(label="Attachments")
        header.set_xalign(0)
        header.add_css_class("title-3")
        box.append(header)

        # Drop zone
        self.drop_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.drop_box.add_css_class("card")
        self.drop_box.set_margin_top(12)
        self.drop_box.set_margin_bottom(12)

        drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        drop_target.connect('drop', self._on_file_dropped)
        self.drop_box.add_controller(drop_target)

        self.drop_box.append(Gtk.Box())  # Top spacer
        self.drop_box.get_first_child().set_size_request(-1, 16)

        icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")
        self.drop_box.append(icon)

        label = Gtk.Label(label="Drop files here or")
        label.add_css_class("dim-label")
        self.drop_box.append(label)

        browse_btn = Gtk.Button(label="Browse Files")
        browse_btn.set_halign(Gtk.Align.CENTER)
        browse_btn.connect('clicked', self._on_browse_clicked)
        self.drop_box.append(browse_btn)

        size_label = Gtk.Label(label="Max 30MB per file")
        size_label.add_css_class("caption")
        size_label.add_css_class("dim-label")
        self.drop_box.append(size_label)

        self.drop_box.append(Gtk.Box())  # Bottom spacer
        self.drop_box.get_last_child().set_size_request(-1, 16)

        box.append(self.drop_box)

        # Attachment list
        self.attachments_list = Gtk.ListBox()
        self.attachments_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.attachments_list.add_css_class("boxed-list")

        self.attachments_scrolled = Gtk.ScrolledWindow()
        self.attachments_scrolled.set_vexpand(True)
        self.attachments_scrolled.set_min_content_height(150)
        self.attachments_scrolled.set_child(self.attachments_list)
        self.attachments_scrolled.set_visible(False)
        box.append(self.attachments_scrolled)

        return box

    # -------------------------------------------------------------------------
    # LOAD MEMO
    # -------------------------------------------------------------------------

    def load_memo(self, memo=None):
        """Load memo for editing, or prepare for new memo"""
        self.current_memo = memo
        self.attachments = []
        self.existing_attachments = []

        # Clear attachment list
        child = self.attachments_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.attachments_list.remove(child)
            child = next_child

        if memo:
            # Edit existing
            self.title_widget.set_title("Edit Memo")
            self.save_icon.set_from_icon_name("document-save-as-symbolic")
            self.save_button.set_tooltip_text("Update memo")
            self.delete_button.set_visible(True)
            self.buffer.set_text(memo.get('content', ''))

            # Load existing attachments
            for attach in memo.get('resources', []) or memo.get('attachments', []):
                self.existing_attachments.append(attach)
                self.attachments_list.append(self._create_existing_attachment_row(attach))
            self._update_attachments_visibility()
        else:
            # New memo
            self.title_widget.set_title("New Memo")
            self.save_icon.set_from_icon_name("document-save-symbolic")
            self.save_button.set_tooltip_text("Save memo")
            self.delete_button.set_visible(False)
            self.buffer.set_text('')
            self.attachments_scrolled.set_visible(False)

        self._update_attachment_badges()
        self.bottom_sheet.set_open(False)

    # -------------------------------------------------------------------------
    # ATTACHMENTS
    # -------------------------------------------------------------------------

    def _on_attach_clicked(self, button):
        """Toggle attachment sheet"""
        self.bottom_sheet.set_open(not self.bottom_sheet.get_open())

    def _on_browse_clicked(self, button):
        """Open file picker"""
        dialog = Gtk.FileChooserNative.new(
            "Choose files to attach",
            self.container.get_root(),
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel"
        )
        dialog.set_select_multiple(True)
        dialog.connect('response', self._on_file_chooser_response)
        dialog.show()

    def _on_file_chooser_response(self, dialog, response):
        """Handle file picker result"""
        if response == Gtk.ResponseType.ACCEPT:
            files = dialog.get_files()
            for i in range(files.get_n_items()):
                self._add_attachment(files.get_item(i))
        dialog.destroy()

    def _on_file_dropped(self, drop_target, value, x, y):
        """Handle drag-and-drop"""
        if isinstance(value, Gio.File):
            self._add_attachment(value)
            return True
        return False

    def _add_attachment(self, file):
        """Add file to new attachments"""
        info = file.query_info("standard::*", Gio.FileQueryInfoFlags.NONE, None)
        size = info.get_size()
        name = info.get_name()

        if size > self.MAX_FILE_SIZE:
            return

        # Skip duplicates
        for a in self.attachments:
            if a['file'].get_path() == file.get_path():
                return

        attachment = {'file': file, 'name': name, 'size': size}
        self.attachments.append(attachment)
        self.attachments_list.append(self._create_new_attachment_row(attachment))
        self._update_attachments_visibility()
        self._update_attachment_badges()

    def _remove_attachment(self, attachment, row):
        """Remove new attachment"""
        self.attachments.remove(attachment)
        self.attachments_list.remove(row)
        self._update_attachments_visibility()
        self._update_attachment_badges()

    def _update_attachment_badges(self):
        """Update badge counts on attach button"""
        saved = len(self.existing_attachments)
        new = len(self.attachments)

        self.saved_badge.set_label(str(saved))
        self.saved_badge.set_visible(saved > 0)

        self.new_badge.set_label(f"+{new}")
        self.new_badge.set_visible(new > 0)

    def _update_attachments_visibility(self):
        """Show list if there are attachments"""
        total = len(self.attachments) + len(self.existing_attachments)
        self.attachments_scrolled.set_visible(total > 0)

    def _create_existing_attachment_row(self, attachment):
        """Row for saved attachment"""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        icon_name = "image-x-generic-symbolic" if 'image' in attachment.get('type', '').lower() else "text-x-generic-symbolic"
        box.append(Gtk.Image.new_from_icon_name(icon_name))

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info.set_hexpand(True)

        name = Gtk.Label(label=attachment.get('filename', 'Unknown'))
        name.set_xalign(0)
        name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        info.append(name)

        size = attachment.get('size', 0)
        if isinstance(size, str):
            size = int(size)
        size_label = Gtk.Label(label=f"{size / 1024:.1f} KB")
        size_label.set_xalign(0)
        size_label.add_css_class("caption")
        size_label.add_css_class("dim-label")
        info.append(size_label)

        box.append(info)

        badge = Gtk.Label(label="Saved")
        badge.add_css_class("caption")
        badge.add_css_class("dim-label")
        box.append(badge)

        row.set_child(box)
        return row

    def _create_new_attachment_row(self, attachment):
        """Row for new attachment (with remove button)"""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        box.append(Gtk.Image.new_from_icon_name("text-x-generic-symbolic"))

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info.set_hexpand(True)

        name = Gtk.Label(label=attachment['name'])
        name.set_xalign(0)
        name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        info.append(name)

        size_label = Gtk.Label(label=f"{attachment['size'] / 1024:.1f} KB")
        size_label.set_xalign(0)
        size_label.add_css_class("caption")
        size_label.add_css_class("dim-label")
        info.append(size_label)

        box.append(info)

        badge = Gtk.Label(label="New")
        badge.add_css_class("caption")
        badge.add_css_class("success")
        box.append(badge)

        remove_btn = Gtk.Button(icon_name="user-trash-symbolic")
        remove_btn.add_css_class("flat")
        remove_btn.connect('clicked', lambda b: self._remove_attachment(attachment, row))
        box.append(remove_btn)

        row.set_child(box)
        return row

    # -------------------------------------------------------------------------
    # SAVE / DELETE
    # -------------------------------------------------------------------------

    def _on_save_clicked(self, button):
        """Trigger save callback"""
        text = self.buffer.get_text(
            self.buffer.get_start_iter(),
            self.buffer.get_end_iter(),
            False
        )
        if self.on_save_callback:
            self.on_save_callback(self.current_memo, text, self.attachments)

    def _on_delete_clicked(self, button):
        """Trigger delete callback"""
        if self.current_memo and self.on_delete_callback:
            self.on_delete_callback(self.current_memo)

    def show_saving(self):
        """Show spinner, disable save"""
        self.save_button.set_sensitive(False)
        self.save_spinner.set_visible(True)
        self.save_spinner.start()

    def hide_saving(self):
        """Hide spinner, enable save"""
        self.save_button.set_sensitive(True)
        self.save_spinner.stop()
        self.save_spinner.set_visible(False)

    # -------------------------------------------------------------------------
    # MARKDOWN STYLING
    # -------------------------------------------------------------------------

    def _create_tags(self):
        """Text tags for inline markdown preview"""
        t = self.buffer.get_tag_table()

        def add(name, **props):
            tag = Gtk.TextTag(name=name)
            for k, v in props.items():
                tag.set_property(k, v)
            t.add(tag)

        add("h1", scale=2.0, weight=Pango.Weight.BOLD)
        add("h2", scale=1.5, weight=Pango.Weight.BOLD)
        add("h3", scale=1.25, weight=Pango.Weight.BOLD)
        add("bold", weight=Pango.Weight.BOLD)
        add("italic", style=Pango.Style.ITALIC)
        add("code", family="monospace", background="#f4f4f4", foreground="#c7254e")
        add("code_block", family="monospace", background="#f6f8fa")
        add("quote", foreground="#666", style=Pango.Style.ITALIC, left_margin=20)
        add("link", foreground="#0366d6", underline=Pango.Underline.SINGLE)
        add("strikethrough", strikethrough=True)
        add("list_bullet", foreground="#0366d6", weight=Pango.Weight.BOLD)
        add("list_number", foreground="#0366d6", weight=Pango.Weight.BOLD)
        add("list_item", left_margin=40, indent=-15)

    def _on_text_changed(self, buffer):
        """Debounced markdown styling"""
        if self._update_timeout:
            GLib.source_remove(self._update_timeout)
        self._update_timeout = GLib.timeout_add(150, self._apply_markdown_styling)

    def _apply_markdown_styling(self):
        """Apply markdown tags to buffer"""
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        self.buffer.remove_all_tags(start, end)

        text = self.buffer.get_text(start, end, False)
        offset = 0

        for line in text.split('\n'):
            length = len(line)

            # Block-level
            if line.startswith('# '):
                self._tag(offset, offset + length, 'h1')
            elif line.startswith('## '):
                self._tag(offset, offset + length, 'h2')
            elif line.startswith('### '):
                self._tag(offset, offset + length, 'h3')
            elif line.startswith('> '):
                self._tag(offset, offset + length, 'quote')
            elif line.startswith('    ') or line.startswith('\t'):
                self._tag(offset, offset + length, 'code_block')
            elif re.match(r'^[\s]*\d+\.\s+', line):
                m = re.match(r'^([\s]*\d+\.\s+)', line)
                if m:
                    self._tag(offset, offset + len(m.group(1)), 'list_number')
                    self._tag(offset, offset + length, 'list_item')
            elif re.match(r'^[\s]*[-*+]\s+', line):
                m = re.match(r'^([\s]*[-*+]\s+)', line)
                if m:
                    self._tag(offset, offset + len(m.group(1)), 'list_bullet')
                    self._tag(offset, offset + length, 'list_item')

            # Inline (skip block-level lines)
            if not line.startswith(('# ', '## ', '### ', '> ', '    ', '\t')):
                for m in re.finditer(r'\*\*(.+?)\*\*', line):
                    self._tag(offset + m.start(), offset + m.end(), 'bold')
                for m in re.finditer(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', line):
                    self._tag(offset + m.start(), offset + m.end(), 'italic')
                for m in re.finditer(r'_(.+?)_', line):
                    self._tag(offset + m.start(), offset + m.end(), 'italic')
                for m in re.finditer(r'`(.+?)`', line):
                    self._tag(offset + m.start(), offset + m.end(), 'code')
                for m in re.finditer(r'~~(.+?)~~', line):
                    self._tag(offset + m.start(), offset + m.end(), 'strikethrough')
                for m in re.finditer(r'\[(.+?)\]\((.+?)\)', line):
                    self._tag(offset + m.start(), offset + m.end(), 'link')

            offset += length + 1

        self._update_timeout = None
        return False

    def _tag(self, start, end, name):
        """Apply tag by name"""
        self.buffer.apply_tag_by_name(
            name,
            self.buffer.get_iter_at_offset(start),
            self.buffer.get_iter_at_offset(end)
        )

    # -------------------------------------------------------------------------
    # AUTO-LIST CONTINUATION
    # -------------------------------------------------------------------------

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Continue lists on Enter"""
        if keyval != Gdk.KEY_Return:
            return False

        cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        line_start = cursor.copy()
        line_start.set_line_offset(0)
        line_text = self.buffer.get_text(line_start, cursor, False)

        # Ordered list: 1. 2. 3.
        m = re.match(r'^(\s*)(\d+)\.\s+(.*)$', line_text)
        if m:
            indent, num, content = m.groups()
            if content.strip():
                self.buffer.insert_at_cursor(f"\n{indent}{int(num)+1}. ")
                return True
            else:
                self.buffer.delete(line_start, cursor)
                return False

        # Unordered list: - * +
        m = re.match(r'^(\s*)([-*+])\s+(.*)$', line_text)
        if m:
            indent, marker, content = m.groups()
            if content.strip():
                self.buffer.insert_at_cursor(f"\n{indent}{marker} ")
                return True
            else:
                self.buffer.delete(line_start, cursor)
                return False

        return False
