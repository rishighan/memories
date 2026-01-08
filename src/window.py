# window.py
# Main window: connection, memo list, editor

import threading
import time
import weakref

from gi.repository import Adw, Gio, GLib, Gtk

from .ui.connection_view import ConnectionView
from .ui.memo_edit_view import MemoEditView
from .ui.memos_view import MemosView
from .ui.preferences import PreferencesWindow
from .ui.search_handler import SearchHandler
from .utils.settings import Settings


@Gtk.Template(resource_path="/org/quasars/memories/window.ui")
class MemoriesWindow(Adw.ApplicationWindow):
    __gtype_name__ = "MemoriesWindow"

    # Connection screen
    main_stack = Gtk.Template.Child()
    url_entry = Gtk.Template.Child()
    token_entry = Gtk.Template.Child()
    connect_button = Gtk.Template.Child()
    status_label = Gtk.Template.Child()

    # Memos list
    memos_container = Gtk.Template.Child()
    scrolled_window = Gtk.Template.Child()
    server_label = Gtk.Template.Child()
    connection_status_label = Gtk.Template.Child()
    memo_count_label = Gtk.Template.Child()
    auto_refresh_label = Gtk.Template.Child()
    search_entry = Gtk.Template.Child()
    search_bar = Gtk.Template.Child()
    search_button = Gtk.Template.Child()
    new_memo_button = Gtk.Template.Child()

    # Edit screen
    memo_edit_content = Gtk.Template.Child()
    memo_edit_title = Gtk.Template.Child()
    edit_back_button = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_css()
        self.api = None
        self.search_handler = None
        self._needs_reload = False
        self._search_query = None
        self._search_results = None
        self._auto_refresh_timeout = None
        self._last_refresh_time = None
        self._last_timer_check = None

        self._setup_views()
        self._connect_signals()
        self._setup_actions()
        self._try_auto_connect()
        
        # Start timer to update "x minutes ago" display and check timer health
        GLib.timeout_add_seconds(30, self._update_refresh_status_display)

    # -------------------------------------------------------------------------
    # SETUP
    # -------------------------------------------------------------------------

    def _load_css(self):
        """Load styles"""
        css = Gtk.CssProvider()
        css.load_from_resource("/org/quasars/memories/style.css")
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _setup_views(self):
        """Initialize views"""
        self.connection_view = ConnectionView(
            self.url_entry, self.token_entry, self.connect_button, self.status_label
        )
        self.connection_view.on_success_callback = self._on_connected

        self.memos_view = MemosView(
            self.memos_container, self.scrolled_window, self.memo_count_label
        )

        self.memo_edit_view = MemoEditView(self.memo_edit_content, self.memo_edit_title)
        self.memo_edit_view.on_save_callback = self._on_save_memo
        self.memo_edit_view.on_delete_callback = self._on_delete_memo

    def _connect_signals(self):
        """Wire up signals"""
        self.new_memo_button.connect("clicked", self._on_new_memo_clicked)
        self.edit_back_button.connect("clicked", self._on_back_clicked)

    def _setup_actions(self):
        """Setup window actions"""
        prefs = Gio.SimpleAction.new("preferences", None)
        prefs.connect("activate", self._on_preferences)
        self.add_action(prefs)

        disconnect = Gio.SimpleAction.new("disconnect", None)
        disconnect.connect("activate", self._on_disconnect)
        disconnect.set_enabled(False)
        self.add_action(disconnect)
        self.disconnect_action = disconnect

    # -------------------------------------------------------------------------
    # CONNECTION
    # -------------------------------------------------------------------------

    def _on_connected(self, api, memos, page_token):
        """Handle connection success"""
        self.api = api
        self.memo_edit_view.api = api
        self.disconnect_action.set_enabled(True)

        self.server_label.set_label("Connected")
        self.connection_status_label.set_label("●")
        self.memo_count_label.set_label(f"{len(memos)} memos")

        self.search_handler = SearchHandler(
            api, self.search_entry, self.search_bar, self.search_button
        )
        self.search_handler.on_results_callback = self._on_search_results

        self.memos_view.load_memos(api, memos, page_token)
        self.memos_view.memo_loader.on_memo_clicked = self._on_memo_clicked
        self.main_stack.set_visible_child_name("memos")
        
        # Set initial refresh time and update display
        self._last_refresh_time = time.time()
        self._update_refresh_status_display()
        
        # Start auto-refresh timer
        self._start_auto_refresh()

    def _on_disconnect(self, action, param):
        """Disconnect from server"""
        # Stop auto-refresh timer
        self._stop_auto_refresh()
        
        # Clean up views to break circular references
        if self.memo_edit_view:
            self.memo_edit_view.cleanup()
            self.memo_edit_view.api = None
        
        if self.memos_view:
            self.memos_view.cleanup()
            self.memos_view.heatmap = None
        
        if self.search_handler:
            self.search_handler.on_results_callback = None
        
        # Clear references
        self.api = None
        self.search_handler = None
        self.disconnect_action.set_enabled(False)
        self._search_query = None
        self._search_results = None
        self._last_refresh_time = None
        self._last_timer_check = None

        # Clear container
        child = self.memos_container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.memos_container.remove(child)
            child = next_child

        self.server_label.set_label("")
        self.connection_status_label.set_label("")
        self.memo_count_label.set_label("")
        self.auto_refresh_label.set_label("")
        self.status_label.set_label("")

        self.main_stack.set_visible_child_name("connection")

    def _try_auto_connect(self):
        """Auto-connect if creds exist"""
        settings = Settings()
        url = settings.get_server_url()
        token = settings.get_api_token()

        if url and token:
            self.connection_view.url_entry.set_text(url)
            self.connection_view.token_entry.set_text(token)
            self.connection_view._on_connect(None)

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------

    def _on_new_memo_clicked(self, button):
        """New memo"""
        self._clear_search_state()
        self.memo_edit_view.load_memo(None)
        self.main_stack.set_visible_child_name("memo_edit")

    def _on_memo_clicked(self, memo):
        """Open memo - fetch fresh first"""
        if not self.api:
            self._load_memo_in_editor(memo)
            return

        def worker():
            ok, fresh = self.api.get_memo(memo.get("name"))
            GLib.idle_add(self._load_memo_in_editor, fresh if ok else memo)

        threading.Thread(target=worker, daemon=True).start()

    def _load_memo_in_editor(self, memo):
        """Load into editor"""
        self.memo_edit_view.load_memo(memo)
        self.main_stack.set_visible_child_name("memo_edit")

    def _on_back_clicked(self, button):
        """Back to list"""
        if self._needs_reload:
            if self._search_query:
                self._perform_search_refresh()
            else:
                self._reload_memos()
            self._needs_reload = False
        elif self._search_query:
            self.memos_view.show_search_results(
                self._search_results, self._search_query
            )

        self.main_stack.set_visible_child_name("memos")

    def _clear_search_state(self):
        """Clear search"""
        self._search_query = None
        self._search_results = None

    # -------------------------------------------------------------------------
    # SEARCH
    # -------------------------------------------------------------------------

    def _on_search_results(self, query, memos):
        """Handle search results"""
        self._search_query = query
        self._search_results = memos if query else None

        if query:
            self.memos_view.show_search_results(memos, query)
        else:
            self.memos_view.restore_all_memos()

    def _perform_search_refresh(self):
        """Re-run search"""
        if not self.api or not self._search_query:
            return

        def worker():
            success, memos, _ = self.api.search_memos(self._search_query)
            GLib.idle_add(self._on_search_refresh_complete, success, memos)

        threading.Thread(target=worker, daemon=True).start()

    def _on_search_refresh_complete(self, success, memos):
        """Update search results"""
        if success:
            self._search_results = memos
            self.memos_view.show_search_results(memos, self._search_query)

    # -------------------------------------------------------------------------
    # SAVE / DELETE
    # -------------------------------------------------------------------------

    def _on_save_memo(self, memo, text, attachments, is_autosave=False):
        """Save memo"""
        if not text.strip() and not memo:
            self._on_back_clicked(None)
            return

        if not self.api:
            return

        existing = self.memo_edit_view.existing_attachments

        def worker():
            if memo:
                if attachments:
                    success, result = self.api.update_memo_with_attachments(
                        memo.get("name"), text, attachments, existing
                    )
                else:
                    success, result = self.api.update_memo(memo.get("name"), text)
            else:
                if attachments:
                    success, result = self.api.create_memo_with_attachments(
                        text, attachments
                    )
                else:
                    success, result = self.api.create_memo(text)

            GLib.idle_add(self._on_save_complete, success, result, is_autosave)

        threading.Thread(target=worker, daemon=True).start()

    def _on_save_complete(self, success, result, is_autosave):
        """Handle save complete"""
        if success:
            # Refetch for fresh metadata
            memo_name = result.get("name") if result else None
            if memo_name and self.api:
                ok, fresh = self.api.get_memo(memo_name)
                if ok:
                    result = fresh

        self.memo_edit_view.on_save_complete(success, result if success else None)

        if success:
            # Mark that list needs reload, but don't navigate away
            self._needs_reload = True

    def _on_delete_memo(self, memo):
        """Delete memo"""
        if not self.api or not memo:
            return

        def worker():
            success = self.api.delete_memo(memo.get("name"))
            GLib.idle_add(self._on_delete_complete, success)

        threading.Thread(target=worker, daemon=True).start()

    def _on_delete_complete(self, success):
        """Handle delete complete"""
        if success:
            self._clear_search_state()
            self._reload_memos()
            self.main_stack.set_visible_child_name("memos")

    # -------------------------------------------------------------------------
    # RELOAD
    # -------------------------------------------------------------------------

    def _reload_memos(self):
        """Refresh memo list"""

        def worker():
            success, memos, page_token = self.api.get_memos()
            GLib.idle_add(self._on_reload_complete, success, memos, page_token)

        threading.Thread(target=worker, daemon=True).start()

    def _on_reload_complete(self, success, memos, page_token):
        """Handle reload"""
        if not success:
            return

        self.memos_view.memo_loader.page_token = page_token
        self.memos_view.memo_loader.load_initial(memos)
        self.memos_view.heatmap.set_memos(memos)
        self.memos_view.loaded_memos = len(memos)
        self.memos_view.total_memos = len(memos) if not page_token else None
        self.memos_view._update_count()

    # -------------------------------------------------------------------------
    # PREFERENCES
    # -------------------------------------------------------------------------

    def _on_preferences(self, action, param):
        """Open preferences"""
        prefs = PreferencesWindow(
            self, on_credentials_changed=self._on_credentials_changed
        )
        prefs.present()

    def _on_credentials_changed(self):
        """Handle cred change or settings change"""
        # Restart auto-refresh timer if connected (settings may have changed)
        if self.api:
            self._start_auto_refresh()
        else:
            self._try_auto_connect()

    # -------------------------------------------------------------------------
    # AUTO-REFRESH
    # -------------------------------------------------------------------------

    def _start_auto_refresh(self):
        """Start or restart auto-refresh timer"""
        # Stop existing timer
        self._stop_auto_refresh()
        
        # Get interval from settings
        settings = Settings()
        interval_minutes = settings.get_auto_refresh_interval()
        
        # Convert minutes to seconds for GLib.timeout_add_seconds
        interval_seconds = interval_minutes * 60
        
        print(f"[DEBUG] Starting auto-refresh timer: {interval_minutes} minutes ({interval_seconds} seconds)")
        
        # Start new timer using timeout_add_seconds for better accuracy
        self._auto_refresh_timeout = GLib.timeout_add_seconds(
            interval_seconds, self._on_auto_refresh
        )
        
        # Track when we last checked the timer
        self._last_timer_check = time.time()
        
        print(f"[DEBUG] Auto-refresh timer ID: {self._auto_refresh_timeout}")

    def _stop_auto_refresh(self):
        """Stop auto-refresh timer"""
        if self._auto_refresh_timeout:
            GLib.source_remove(self._auto_refresh_timeout)
            self._auto_refresh_timeout = None

    def _on_auto_refresh(self):
        """Auto-refresh callback"""
        print(f"[DEBUG] Auto-refresh timer fired")
        
        # Update last timer check time
        self._last_timer_check = time.time()
        
        # Only refresh if we're on the memos view and not editing
        current_page = self.main_stack.get_visible_child_name()
        if current_page != "memos" or not self.api:
            print(f"[DEBUG] Skipping refresh - current_page={current_page}, api={self.api is not None}")
            # Keep timer running
            return True
        
        # Don't refresh if in search mode
        if self._search_query:
            print(f"[DEBUG] Skipping refresh - in search mode")
            # Keep timer running
            return True
        
        print(f"[DEBUG] Performing auto-refresh...")
        
        # Perform refresh in background
        def worker():
            success, memos, page_token = self.api.get_memos()
            GLib.idle_add(self._on_auto_refresh_complete, success, memos, page_token)
        
        threading.Thread(target=worker, daemon=True).start()
        
        # Keep timer running
        return True

    def _on_auto_refresh_complete(self, success, memos, page_token):
        """Handle auto-refresh complete"""
        print(f"[DEBUG] Auto-refresh complete - success={success}, memos={len(memos) if memos else 0}")
        
        if not success or not self.memos_view.memo_loader:
            print(f"[DEBUG] Skipping update - success={success}, memo_loader={self.memos_view.memo_loader is not None}")
            return
        
        # Update last refresh time
        self._last_refresh_time = time.time()
        self._update_refresh_status_display()
        
        print(f"[DEBUG] Updating memo list with {len(memos)} memos")
        
        # Silently update the list
        self.memos_view.memo_loader.page_token = page_token
        self.memos_view.memo_loader.load_initial(memos)
        if self.memos_view.heatmap:
            self.memos_view.heatmap.set_memos(memos)
        self.memos_view.loaded_memos = len(memos)
        self.memos_view.total_memos = len(memos) if not page_token else None
        self.memos_view._update_count()
    
    def _update_refresh_status_display(self):
        """Update the auto-refresh status label and check timer health"""
        # Check if timer might have died (e.g., after system sleep)
        if self.api and self._last_timer_check:
            elapsed_since_check = time.time() - self._last_timer_check
            settings = Settings()
            interval_seconds = settings.get_auto_refresh_interval() * 60
            
            # If more than 2x the interval has passed without timer firing, restart it
            if elapsed_since_check > (interval_seconds * 2):
                print(f"[DEBUG] Timer appears dead (no fire in {elapsed_since_check}s), restarting...")
                self._start_auto_refresh()
        
        if not self._last_refresh_time:
            return True
        
        elapsed = time.time() - self._last_refresh_time
        minutes = int(elapsed / 60)
        
        if minutes == 0:
            status_text = "Auto-refreshed just now"
        elif minutes == 1:
            status_text = "Auto-refreshed 1 minute ago"
        else:
            status_text = f"Auto-refreshed {minutes} minutes ago"
        
        self.auto_refresh_label.set_label(status_text)
        
        # Keep the timer running
        return True
