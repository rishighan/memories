# ui/view_base.py
# Base class for views with automatic cleanup of resources

from gi.repository import GLib


class ViewBase:
    """Base class for views with resource cleanup"""

    def __init__(self):
        self._timeouts = []
        self._signal_handlers = []
        self._callbacks = []

    def add_timeout(self, timeout_id):
        """Track a GLib timeout for cleanup"""
        if timeout_id:
            self._timeouts.append(timeout_id)
        return timeout_id

    def remove_timeout(self, timeout_id):
        """Remove and cleanup a specific timeout"""
        if timeout_id and timeout_id in self._timeouts:
            GLib.source_remove(timeout_id)
            self._timeouts.remove(timeout_id)

    def add_signal(self, obj, handler_id):
        """Track a signal handler for cleanup"""
        if obj and handler_id:
            self._signal_handlers.append((obj, handler_id))
        return handler_id

    def cleanup(self):
        """Clean up all tracked resources"""
        # Remove all timeouts
        for timeout_id in self._timeouts:
            try:
                GLib.source_remove(timeout_id)
            except Exception:
                pass  # Timeout may have already fired
        self._timeouts.clear()

        # Disconnect all signal handlers
        for obj, handler_id in self._signal_handlers:
            try:
                obj.disconnect(handler_id)
            except Exception:
                pass  # Object may have been destroyed
        self._signal_handlers.clear()

        # Clear callback references
        self._callbacks.clear()
