# settings.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gio


class Settings:
    """Handle app settings persistence"""

    def __init__(self):
        self.settings = Gio.Settings.new('org.quasars.memories')

    def get_server_url(self):
        return self.settings.get_string('server-url')

    def set_server_url(self, url):
        self.settings.set_string('server-url', url)

    def get_api_token(self):
        return self.settings.get_string('api-token')

    def set_api_token(self, token):
        self.settings.set_string('api-token', token)
