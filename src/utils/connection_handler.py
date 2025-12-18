# utils/connection_handler.py
# Async API connection: test, auth, fetch initial memos

import threading

from gi.repository import GLib

from ..api.memos_api import MemosAPI


class ConnectionHandler:
    """Async API connection handler"""

    @staticmethod
    def connect(base_url, token, on_success, on_failure):
        """
        Connect to Memos API in background thread.
        on_success(api, memos, page_token, user_info)
        on_failure(message)
        """

        def worker():
            try:
                api = MemosAPI(base_url, token)

                # Test connection
                ok, msg = api.test_connection()
                if not ok:
                    GLib.idle_add(on_failure, msg)
                    return

                # Get user info
                user_info = api.get_user_info()

                # Fetch initial memos
                ok, memos, page_token = api.get_memos()
                if not ok:
                    GLib.idle_add(on_failure, "Failed to load memos")
                    return

                GLib.idle_add(on_success, api, memos, page_token, user_info)

            except Exception as e:
                GLib.idle_add(on_failure, str(e))

        threading.Thread(target=worker, daemon=True).start()
