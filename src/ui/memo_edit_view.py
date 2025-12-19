# ui/memo_edit_view.py
# Memo editor: floating toolbar, attachments, autosave, metadata chips

import re
import threading

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango


class MemoEditView:
    """Memo editor with autosave"""

    MAX_FILE_SIZE = 30 * 1024 * 1024
    AUTOSAVE_DELAY = 2000

    def __init__(self, container, title_widget):
        self.container = container
        self.title_widget = title_widget
        self.api = None
        self.current_memo = None
        self.attachments = []
        self.existing_attachments = []
        self.on_save_callback = None
        self.on_delete_callback = None

        # Autosave state
        self._autosave_timeout = None
        self._last_saved_content = None
        self._update_timeout = None
        self._ui_initialized = False

        self._setup_ui()

    # -------------------------------------------------------------------------
    # UI SETUP
    # -------------------------------------------------------------------------

    def _setup_ui(self):
        """Build UI: overlay with text editor + floating toolbar"""
        if self._ui_initialized:
            return
        self._clear_container()

        # Text editor
        self.text_view = Gtk.TextView()
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_left_margin(20)
        self.text_view.set_right_margin(20)
        self.text_view.set_top_margin(80)
        self.text_view.set_bottom_margin(20)
        self.buffer = self.text_view.get_buffer()
        self._create_tags()
        self.buffer.connect("changed", self._on_text_changed)

        # Key handler for auto-list
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.text_view.add_controller(key_ctrl)

        # Scrolled text area
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.text_view)

        # Metadata container (tags + other metadata)
        self.metadata_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=8
        )
        self.metadata_container.set_margin_start(20)
        self.metadata_container.set_margin_end(20)
        self.metadata_container.set_margin_top(12)
        self.metadata_container.set_margin_bottom(12)
        self.metadata_container.set_visible(False)

        # Tags row
        self.tags_box = Adw.WrapBox()
        self.tags_box.set_line_spacing(4)
        self.tags_box.set_child_spacing(4)
        self.tags_box.set_halign(Gtk.Align.START)
        self.tags_box.add_css_class("metadata-chips")
        self.metadata_container.append(self.tags_box)

        # Other metadata row
        self.metadata_box = Adw.WrapBox()
        self.metadata_box.set_line_spacing(4)
        self.metadata_box.set_child_spacing(4)
        self.metadata_box.set_halign(Gtk.Align.START)
        self.metadata_box.add_css_class("metadata-chips")
        self.metadata_container.append(self.metadata_box)

        # Wrap scrolled + metadata
        editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        editor_box.append(scrolled)
        editor_box.append(self.metadata_container)

        # Bottom sheet for attachments
        self.bottom_sheet = Adw.BottomSheet()
        self.bottom_sheet.set_content(editor_box)
        self.bottom_sheet.set_sheet(self._create_attachments_sheet())
        self.bottom_sheet.set_open(False)
        self.bottom_sheet.set_show_drag_handle(True)

        # Overlay: sheet + floating toolbar
        overlay = Gtk.Overlay()
        overlay.set_child(self.bottom_sheet)
        self.floating_toolbar = self._create_toolbar()
        self.floating_toolbar.set_halign(Gtk.Align.CENTER)
        self.floating_toolbar.set_valign(Gtk.Align.START)
        self.floating_toolbar.set_margin_top(12)
        overlay.add_overlay(self.floating_toolbar)

        self.container.append(overlay)
        self._ui_initialized = True

    def _clear_container(self):
        """Remove all children"""
        child = self.container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.container.remove(child)
            child = next_child

    def _create_toolbar(self):
        """Floating toolbar: attach, save, delete, status"""
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.add_css_class("card")
        toolbar.add_css_class("toolbar")

        # Attach button + badges
        self.attach_button = Gtk.Button()
        self.attach_button.add_css_class("flat")
        self.attach_button.set_tooltip_text("Attachments")
        self.attach_button.connect("clicked", self._on_attach_clicked)

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

        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # Save button
        self.save_button = Gtk.Button()
        self.save_button.add_css_class("flat")
        self.save_icon = Gtk.Image.new_from_icon_name("document-save-symbolic")
        self.save_button.set_child(self.save_icon)
        self.save_button.set_tooltip_text("Save memo")
        self.save_button.connect("clicked", self._on_save_clicked)
        toolbar.append(self.save_button)

        # Delete button
        self.delete_button = Gtk.Button()
        self.delete_button.add_css_class("flat")
        self.delete_button.set_child(
            Gtk.Image.new_from_icon_name("user-trash-symbolic")
        )
        self.delete_button.set_tooltip_text("Delete memo")
        self.delete_button.set_visible(False)
        self.delete_button.connect("clicked", self._on_delete_clicked)
        toolbar.append(self.delete_button)

        # Autosave status
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.status_box.set_margin_start(4)
        self.status_box.set_margin_end(4)
        self.status_box.set_visible(False)

        self.status_spinner = Gtk.Spinner()
        self.status_spinner.set_size_request(16, 16)
        self.status_box.append(self.status_spinner)

        self.status_icon = Gtk.Image()
        self.status_icon.set_pixel_size(16)
        self.status_icon.set_visible(False)
        self.status_box.append(self.status_icon)

        self.status_label = Gtk.Label()
        self.status_label.add_css_class("caption")
        self.status_label.add_css_class("dim-label")
        self.status_box.append(self.status_label)

        toolbar.append(self.status_box)

        return toolbar

    def _create_attachments_sheet(self):
        """Bottom sheet: drop zone + attachment list"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)

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
        drop_target.connect("drop", self._on_file_dropped)
        self.drop_box.add_controller(drop_target)

        icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
        icon.set_margin_top(16)
        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")
        self.drop_box.append(icon)

        lbl = Gtk.Label(label="Drop files here or")
        lbl.add_css_class("dim-label")
        self.drop_box.append(lbl)

        browse_btn = Gtk.Button(label="Browse Files")
        browse_btn.set_halign(Gtk.Align.CENTER)
        browse_btn.connect("clicked", self._on_browse_clicked)
        self.drop_box.append(browse_btn)

        size_lbl = Gtk.Label(label="Max 30MB per file")
        size_lbl.add_css_class("caption")
        size_lbl.add_css_class("dim-label")
        size_lbl.set_margin_bottom(16)
        self.drop_box.append(size_lbl)

        box.append(self.drop_box)

        # Attachment list
        self.attachments_list = Gtk.ListBox()
        self.attachments_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.attachments_list.add_css_class("boxed-list")

        self.attachments_scrolled = Gtk.ScrolledWindow()
        self.attachments_scrolled.set_vexpand(False)
        self.attachments_scrolled.set_max_content_height(300)
        self.attachments_scrolled.set_propagate_natural_height(True)
        self.attachments_scrolled.set_child(self.attachments_list)
        self.attachments_scrolled.set_visible(False)
        box.append(self.attachments_scrolled)

        return box

    # -------------------------------------------------------------------------
    # LOAD MEMO
    # -------------------------------------------------------------------------

    def load_memo(self, memo=None):
        """Load memo for editing or create new"""
        self.current_memo = memo
        self.attachments = []
        self.existing_attachments = []

        # Clear autosave timeout
        if self._autosave_timeout:
            GLib.source_remove(self._autosave_timeout)
            self._autosave_timeout = None

        # Clear update timeout
        if self._update_timeout:
            GLib.source_remove(self._update_timeout)
            self._update_timeout = None

        # Clear attachments
        child = self.attachments_list.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.attachments_list.remove(child)
            child = next_child

        if memo:
            self.title_widget.set_title("Edit Memo")
            self.delete_button.set_visible(True)
            self.buffer.set_text(memo.get("content", ""))

            # Existing attachments
            for a in memo.get("resources", []) or memo.get("attachments", []):
                self.existing_attachments.append(a)
                self.attachments_list.append(self._create_existing_attachment_row(a))
            self._update_attachments_visibility()
        else:
            self.title_widget.set_title("New Memo")
            self.delete_button.set_visible(False)
            self.buffer.set_text("")
            self.attachments_scrolled.set_visible(False)

        self._last_saved_content = self._get_content()
        self._update_metadata(memo)
        self._update_attachment_badges()
        self.bottom_sheet.set_open(False)

    # -------------------------------------------------------------------------
    # AUTOSAVE
    # -------------------------------------------------------------------------

    def _schedule_autosave(self):
        """Reset autosave timer"""
        if self._autosave_timeout:
            GLib.source_remove(self._autosave_timeout)
        self._autosave_timeout = GLib.timeout_add(self.AUTOSAVE_DELAY, self._autosave)

    def _autosave(self):
        """Auto-save if changed"""
        self._autosave_timeout = None
        content = self._get_content()

        if content == self._last_saved_content:
            return False
        if not self.current_memo and not content.strip():
            return False

        self._do_save(content, autosave=True)
        return False

    def _do_save(self, content, autosave=False):
        """Execute save"""
        self._update_save_indicator("saving")
        attachments = [] if autosave else self.attachments

        if self.on_save_callback:
            self.on_save_callback(self.current_memo, content, attachments, autosave)

    def on_save_complete(self, success, memo=None):
        """Called after save completes"""
        if success:
            self._last_saved_content = self._get_content()
            self._update_save_indicator("saved")

            if memo:
                self.current_memo = memo
                self._update_metadata(memo)
                self.delete_button.set_visible(True)
        else:
            self._update_save_indicator("error")

    def _update_save_indicator(self, state):
        """Update toolbar status"""
        self.status_box.set_visible(True)

        if state == "saving":
            self.status_spinner.set_visible(True)
            self.status_spinner.start()
            self.status_icon.set_visible(False)
            self.status_label.set_label("Autosaving...")
            self.save_button.set_sensitive(False)
        elif state == "saved":
            self.status_spinner.stop()
            self.status_spinner.set_visible(False)
            self.status_icon.set_from_icon_name("object-select-symbolic")
            self.status_icon.set_visible(True)
            self.status_label.set_label("Saved")
            self.save_button.set_sensitive(True)
            GLib.timeout_add(3000, self._clear_status)
        elif state == "error":
            self.status_spinner.stop()
            self.status_spinner.set_visible(False)
            self.status_icon.set_from_icon_name("dialog-warning-symbolic")
            self.status_icon.set_visible(True)
            self.status_label.set_label("Failed")
            self.save_button.set_sensitive(True)
            GLib.timeout_add(3000, self._clear_status)

    def _clear_status(self):
        """Hide status"""
        self.status_box.set_visible(False)
        self.status_label.set_label("")
        return False

    def _get_content(self):
        """Get buffer text"""
        return self.buffer.get_text(
            self.buffer.get_start_iter(), self.buffer.get_end_iter(), False
        )

    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------

    def _update_metadata(self, memo):
        """Populate metadata chips"""
        for box in [self.tags_box, self.metadata_box]:
            while child := box.get_first_child():
                box.remove(child)

        if not memo:
            self.metadata_container.set_visible(False)
            return

        has_tags = False
        has_metadata = False

        # Tags (max 3)
        tags = memo.get("tags", [])
        if tags:
            for tag in tags[:3]:
                self.tags_box.append(
                    self._create_chip("folder-symbolic", f"#{tag}", "tag")
                )
            if len(tags) > 3:
                self.tags_box.append(
                    self._create_chip(None, f"+{len(tags) - 3} more", "dim")
                )
            has_tags = True

        # Pinned
        if memo.get("pinned"):
            self.metadata_box.append(
                self._create_chip("view-pin-symbolic", "Pinned", "accent")
            )
            has_metadata = True

        # Relations
        relations = memo.get("relations", [])
        if relations:
            self.metadata_box.append(
                self._create_chip(
                    "insert-link-symbolic", f"{len(relations)} links", "dim"
                )
            )
            has_metadata = True

        # Reactions
        reactions = memo.get("reactions", [])
        if reactions:
            total = (
                sum(r.get("count", 1) for r in reactions)
                if isinstance(reactions[0], dict)
                else len(reactions)
            )
            self.metadata_box.append(
                self._create_chip("face-smile-symbolic", f"{total} reactions", "dim")
            )
            has_metadata = True

        self.tags_box.set_visible(has_tags)
        self.metadata_box.set_visible(has_metadata)
        self.metadata_container.set_visible(has_tags or has_metadata)

        # Fetch comments async
        if self.api and memo.get("name"):
            self._fetch_comments(memo.get("name"))

    def _fetch_comments(self, memo_name):
        """Fetch comments in background"""

        def worker():
            comments = self.api.get_memo_comments(memo_name)
            GLib.idle_add(self._on_comments_loaded, comments)

        threading.Thread(target=worker, daemon=True).start()

    def _on_comments_loaded(self, comments):
        """Add comments chip"""
        if comments:
            self.metadata_box.append(
                self._create_chip(
                    "user-available-symbolic", f"{len(comments)} comments", "dim"
                )
            )
            self.metadata_box.set_visible(True)
            self.metadata_container.set_visible(True)

    def _create_chip(self, icon_name, label_text, style="default"):
        """Create pill button"""
        button = Gtk.Button()
        button.add_css_class("pill")
        button.add_css_class(f"chip-{style}")

        if icon_name:
            content = Adw.ButtonContent()
            content.set_icon_name(icon_name)
            content.set_label(label_text)
            button.set_child(content)
        else:
            button.set_label(label_text)

        return button

    # -------------------------------------------------------------------------
    # ATTACHMENTS
    # -------------------------------------------------------------------------

    def _on_attach_clicked(self, button):
        self.bottom_sheet.set_open(not self.bottom_sheet.get_open())

    def _on_browse_clicked(self, button):
        dialog = Gtk.FileChooserNative.new(
            "Choose files",
            self.container.get_root(),
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel",
        )
        dialog.set_select_multiple(True)
        dialog.connect("response", self._on_file_chooser_response)
        dialog.show()

    def _on_file_chooser_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            for i in range(dialog.get_files().get_n_items()):
                self._add_attachment(dialog.get_files().get_item(i))
        dialog.destroy()

    def _on_file_dropped(self, drop_target, value, x, y):
        if isinstance(value, Gio.File):
            self._add_attachment(value)
            return True
        return False

    def _add_attachment(self, file):
        info = file.query_info("standard::*", Gio.FileQueryInfoFlags.NONE, None)
        size, name = info.get_size(), info.get_name()

        if size > self.MAX_FILE_SIZE:
            return
        if any(a["file"].get_path() == file.get_path() for a in self.attachments):
            return

        attachment = {"file": file, "name": name, "size": size}
        self.attachments.append(attachment)
        self.attachments_list.append(self._create_new_attachment_row(attachment))
        self._update_attachments_visibility()
        self._update_attachment_badges()

    def _remove_attachment(self, attachment, row):
        self.attachments.remove(attachment)
        self.attachments_list.remove(row)
        self._update_attachments_visibility()
        self._update_attachment_badges()

    def _update_attachment_badges(self):
        saved, new = len(self.existing_attachments), len(self.attachments)
        self.saved_badge.set_label(str(saved))
        self.saved_badge.set_visible(saved > 0)
        self.new_badge.set_label(f"+{new}")
        self.new_badge.set_visible(new > 0)

    def _update_attachments_visibility(self):
        self.attachments_scrolled.set_visible(
            len(self.attachments) + len(self.existing_attachments) > 0
        )

    def _create_existing_attachment_row(self, attachment):
        """Row for saved attachment"""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        icon = (
            "image-x-generic-symbolic"
            if "image" in attachment.get("type", "").lower()
            else "text-x-generic-symbolic"
        )
        box.append(Gtk.Image.new_from_icon_name(icon))

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info.set_hexpand(True)

        name = Gtk.Label(label=attachment.get("filename", "Unknown"))
        name.set_xalign(0)
        name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        info.append(name)

        size = attachment.get("size", 0)
        size = int(size) if isinstance(size, str) else size
        size_lbl = Gtk.Label(label=f"{size / 1024:.1f} KB")
        size_lbl.set_xalign(0)
        size_lbl.add_css_class("caption")
        size_lbl.add_css_class("dim-label")
        info.append(size_lbl)

        box.append(info)

        badge = Gtk.Label(label="Saved")
        badge.add_css_class("caption")
        badge.add_css_class("dim-label")
        box.append(badge)

        row.set_child(box)
        return row

    def _create_new_attachment_row(self, attachment):
        """Row for new attachment"""
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        box.append(Gtk.Image.new_from_icon_name("text-x-generic-symbolic"))

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info.set_hexpand(True)

        name = Gtk.Label(label=attachment["name"])
        name.set_xalign(0)
        name.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        info.append(name)

        size_lbl = Gtk.Label(label=f"{attachment['size'] / 1024:.1f} KB")
        size_lbl.set_xalign(0)
        size_lbl.add_css_class("caption")
        size_lbl.add_css_class("dim-label")
        info.append(size_lbl)

        box.append(info)

        badge = Gtk.Label(label="New")
        badge.add_css_class("caption")
        badge.add_css_class("success")
        box.append(badge)

        remove_btn = Gtk.Button(icon_name="user-trash-symbolic")
        remove_btn.add_css_class("flat")
        remove_btn.connect(
            "clicked", lambda b: self._remove_attachment(attachment, row)
        )
        box.append(remove_btn)

        row.set_child(box)
        return row

    # -------------------------------------------------------------------------
    # SAVE / DELETE
    # -------------------------------------------------------------------------

    def _on_save_clicked(self, button):
        self._do_save(self._get_content(), autosave=False)

    def _on_delete_clicked(self, button):
        if self.current_memo and self.on_delete_callback:
            self.on_delete_callback(self.current_memo)

    # -------------------------------------------------------------------------
    # MARKDOWN
    # -------------------------------------------------------------------------

    def _create_tags(self):
        """Text tags for markdown"""
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
        """Markdown styling + autosave"""
        if self._update_timeout:
            GLib.source_remove(self._update_timeout)
        self._update_timeout = GLib.timeout_add(50, self._apply_markdown_styling)

        self._schedule_autosave()

    def _apply_markdown_styling(self):
        """Apply markdown tags"""
        start, end = self.buffer.get_start_iter(), self.buffer.get_end_iter()
        self.buffer.remove_all_tags(start, end)

        text = self.buffer.get_text(start, end, False)
        offset = 0

        for line in text.split("\n"):
            length = len(line)

            if line.startswith("# "):
                self._tag(offset, offset + length, "h1")
            elif line.startswith("## "):
                self._tag(offset, offset + length, "h2")
            elif line.startswith("### "):
                self._tag(offset, offset + length, "h3")
            elif line.startswith("> "):
                self._tag(offset, offset + length, "quote")
            elif line.startswith("    ") or line.startswith("\t"):
                self._tag(offset, offset + length, "code_block")
            elif m := re.match(r"^([\s]*\d+\.\s+)", line):
                self._tag(offset, offset + len(m.group(1)), "list_number")
                self._tag(offset, offset + length, "list_item")
            elif m := re.match(r"^([\s]*[-*+]\s+)", line):
                self._tag(offset, offset + len(m.group(1)), "list_bullet")
                self._tag(offset, offset + length, "list_item")

            if not line.startswith(("# ", "## ", "### ", "> ", "    ", "\t")):
                for m in re.finditer(r"\*\*(.+?)\*\*", line):
                    self._tag(offset + m.start(), offset + m.end(), "bold")
                for m in re.finditer(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", line):
                    self._tag(offset + m.start(), offset + m.end(), "italic")
                for m in re.finditer(r"_(.+?)_", line):
                    self._tag(offset + m.start(), offset + m.end(), "italic")
                for m in re.finditer(r"`(.+?)`", line):
                    self._tag(offset + m.start(), offset + m.end(), "code")
                for m in re.finditer(r"~~(.+?)~~", line):
                    self._tag(offset + m.start(), offset + m.end(), "strikethrough")
                for m in re.finditer(r"\[(.+?)\]\((.+?)\)", line):
                    self._tag(offset + m.start(), offset + m.end(), "link")

            offset += length + 1

        self._update_timeout = None
        return False

    def _tag(self, start, end, name):
        self.buffer.apply_tag_by_name(
            name,
            self.buffer.get_iter_at_offset(start),
            self.buffer.get_iter_at_offset(end),
        )

    # -------------------------------------------------------------------------
    # AUTO-LIST
    # -------------------------------------------------------------------------

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Continue lists on Enter"""
        if keyval != Gdk.KEY_Return:
            return False

        cursor = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        line_start = cursor.copy()
        line_start.set_line_offset(0)
        line_text = self.buffer.get_text(line_start, cursor, False)

        if m := re.match(r"^(\s*)(\d+)\.\s+(.*)$", line_text):
            indent, num, content = m.groups()
            if content.strip():
                self.buffer.insert_at_cursor(f"\n{indent}{int(num)+1}. ")
                return True
            self.buffer.delete(line_start, cursor)
            return False

        if m := re.match(r"^(\s*)([-*+])\s+(.*)$", line_text):
            indent, marker, content = m.groups()
            if content.strip():
                self.buffer.insert_at_cursor(f"\n{indent}{marker} ")
                return True
            self.buffer.delete(line_start, cursor)
            return False

        return False
