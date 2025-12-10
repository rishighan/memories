# window.py
#
# Copyright 2025 Rishi Ghan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk, GLib
import threading
from .memos_api import MemosAPI


@Gtk.Template(resource_path='/org/quasars/memories/window.ui')
class MemoriesWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MemoriesWindow'

    url_entry = Gtk.Template.Child()
    token_entry = Gtk.Template.Child()
    connect_button = Gtk.Template.Child()
    status_label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.url_entry.set_text('https://notes.rishighan.com')
        self.connect_button.connect('clicked', self.on_connect_clicked)

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
                return success, message, user_info
            return success, message, None

        def on_complete(success, message, user_info):
            if success and user_info:
                username = user_info.get('username', 'Unknown')
                self.status_label.set_markup(
                    f'<span foreground="#26a269">✓ Connected successfully!</span>\n'
                    f'<span size="small">Logged in as: <b>{username}</b></span>'
                )
            elif success:
                self.status_label.set_markup('<span foreground="#26a269">✓ Connected successfully!</span>')
            else:
                self.status_label.set_markup(
                    f'<span foreground="#e01b24">✗ Connection failed</span>\n'
                    f'<span size="small">{message}</span>'
                )
            self.connect_button.set_sensitive(True)

        def worker():
            result = test_connection()
            GLib.idle_add(lambda: on_complete(*result))

        threading.Thread(target=worker, daemon=True).start()
