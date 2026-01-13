# settings.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gio


class Settings:
    """Handle app settings persistence"""

    def __init__(self):
        self.settings = Gio.Settings.new("org.quasars.memories")

    def get_server_url(self):
        return self.settings.get_string("server-url")

    def set_server_url(self, url):
        self.settings.set_string("server-url", url)

    def get_api_token(self):
        return self.settings.get_string("api-token")

    def set_api_token(self, token):
        self.settings.set_string("api-token", token)

    def get_auto_refresh_interval(self):
        """Get auto-refresh interval in minutes (5, 10, or 15)"""
        interval = self.settings.get_int("auto-refresh-interval")
        # Validate and default to 5 if invalid
        if interval not in [5, 10, 15]:
            interval = 5
            self.set_auto_refresh_interval(interval)
        return interval

    def set_auto_refresh_interval(self, interval):
        """Set auto-refresh interval (must be 5, 10, or 15)"""
        if interval in [5, 10, 15]:
            self.settings.set_int("auto-refresh-interval", interval)
    
    def clear_credentials(self):
        """Clear stored server URL and API token"""
        self.settings.set_string("server-url", "")
        self.settings.set_string("api-token", "")
