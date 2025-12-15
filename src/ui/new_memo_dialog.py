# ui/new_memo_dialog.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk


class NewMemoDialog(Adw.Dialog):
    """Dialog for creating a new memo"""

    def __init__(self):
        super().__init__()

        self.set_content_width(600)
        self.set_content_height(400)

        # Create text view
        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_left_margin(12)
        self.text_view.set_right_margin(12)
        self.text_view.set_top_margin(12)
        self.text_view.set_bottom_margin(12)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self.text_view)

        # Save button
        self.save_button = Gtk.Button(label="Save")
        self.save_button.add_css_class("suggested-action")

        # Cancel button
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect('clicked', lambda b: self.close())

        # Header
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="New Memo"))
        header.pack_start(cancel_button)
        header.pack_end(self.save_button)

        # Toolbar view
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(scrolled)

        self.set_child(toolbar_view)

        self.on_save_callback = None
        self.save_button.connect('clicked', self._on_save)

    def _on_save(self, button):
        """Handle save button click"""
        buffer = self.text_view.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

        if self.on_save_callback:
            self.on_save_callback(text)

        # Clear and close
        buffer.set_text('')
        self.close()

    def clear(self):
        """Clear the text view"""
        buffer = self.text_view.get_buffer()
        buffer.set_text('')
