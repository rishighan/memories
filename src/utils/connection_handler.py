# connection_handler.py
#
# Copyright 2025 Rishi Ghan
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import GLib
import threading
from ..api.memos_api import MemosAPI


class ConnectionHandler:
    """Handles API connection and authentication"""

    @staticmethod
    def connect(base_url, token, on_success, on_failure):
        """
        Connect to Memos API

        Args:
            base_url: Server URL
            token: API token
            on_success: Callback(api, memos, page_token, user_info)
            on_failure: Callback(message)
        """
        def worker():
            try:
                api = MemosAPI(base_url, token)
                success, message = api.test_connection()

                if not success:
                    GLib.idle_add(lambda: on_failure(message))
                    return

                user_info = api.get_user_info()
                memos_success, memos, page_token = api.get_memos()

                if not memos_success:
                    GLib.idle_add(lambda: on_failure("Failed to load memos"))
                    return

                GLib.idle_add(lambda: on_success(api, memos, page_token, user_info))

            except Exception as e:
                GLib.idle_add(lambda: on_failure(str(e)))

        threading.Thread(target=worker, daemon=True).start()
