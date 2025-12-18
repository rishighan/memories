# window.py
# Main application window: connection, memo list, memo editor

from gi.repository import Adw, Gtk, GLib, Gio
import threading
from .ui.connection_view import ConnectionView
from .ui.memos_view import MemosView
from .ui.search_handler import SearchHandler
from .ui.memo_edit_view import MemoEditView
from .ui.preferences import PreferencesWindow
from .utils.settings import Settings


@Gtk.Template(resource_path='/org/quasars/memories/window.ui')
class MemoriesWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MemoriesWindow'

    # Connection screen
    main_stack = Gtk.Template.Child()
    url_entry = Gtk.Template.Child()
    token_entry = Gtk.Template.Child()
    connect_button = Gtk.Template.Child()
    status_label = Gtk.Template.Child()

    # Memos list screen
    memos_container = Gtk.Template.Child()
    scrolled_window = Gtk.Template.Child()
    server_label = Gtk.Template.Child()
    connection_status_label = Gtk.Template.Child()
    memo_count_label = Gtk.Template.Child()
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
        self._setup_views()
        self._connect_signals()
        self._needs_reload = False
        # Auto-connect if credentials exist
        self._try_auto_connect()
        self._setup_actions()

        # Search Results State
        self._search_query = None
        self._search_results = None

    # -------------------------------------------------------------------------
    # SETUP
    # -------------------------------------------------------------------------

    def _load_css(self):
        """Load application styles"""
        css = Gtk.CssProvider()
        css.load_from_resource('/org/quasars/memories/style.css')
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _setup_views(self):
        """Initialize all views"""
        self.connection_view = ConnectionView(
            self.url_entry, self.token_entry,
            self.connect_button, self.status_label
        )
        self.connection_view.on_success_callback = self._on_connected

        self.memos_view = MemosView(
            self.memos_container, self.scrolled_window, self.memo_count_label
        )

        self.memo_edit_view = MemoEditView(
            self.memo_edit_content, self.memo_edit_title
        )
        self.memo_edit_view.on_save_callback = self._on_save_memo
        self.memo_edit_view.on_delete_callback = self._on_delete_memo

    def _connect_signals(self):
        """Wire up button signals"""
        self.new_memo_button.connect('clicked', self._on_new_memo_clicked)
        self.edit_back_button.connect('clicked', self._on_back_clicked)

    # -------------------------------------------------------------------------
    # CONNECTION
    # -------------------------------------------------------------------------

    def _on_connected(self, api, memos, page_token):
        """Handle successful API connection"""
        self.api = api
        self.memo_edit_view.api = api
        self.disconnect_action.set_enabled(True)

        # Status bar
        self.server_label.set_label(f"Connected to {api.base_url}")
        self.connection_status_label.set_label("●")
        self.connection_status_label.set_tooltip_text("Connected")
        self.memo_count_label.set_label(f"{len(memos)} memos")

        # Search
        self.search_handler = SearchHandler(
            api, self.search_entry, self.search_bar, self.search_button
        )
        self.search_handler.on_results_callback = self._on_search_results

        # Load memos
        self.memos_view.load_memos(api, memos, page_token)
        self.memos_view.memo_loader.on_memo_clicked = self._on_memo_clicked
        self.main_stack.set_visible_child_name('memos')

    def _on_disconnect(self, action, param):
        """Disconnect from server"""
        self.api = None
        self.memo_edit_view.api = None
        self.search_handler = None
        self.disconnect_action.set_enabled(False)
        self.memos_view.heatmap = None

        # Clear memos container
        child = self.memos_container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.memos_container.remove(child)
            child = next_child

        # Reset status bar
        self.server_label.set_label("")
        self.connection_status_label.set_label("")
        self.memo_count_label.set_label("")

        # Clear connection status
        self.status_label.set_label("")

        # Show connection screen
        self.main_stack.set_visible_child_name('connection')

    # -------------------------------------------------------------------------
    # NAVIGATION
    # -------------------------------------------------------------------------

    def _on_new_memo_clicked(self, button):
        """New memo → edit screen"""
        self.memo_edit_view.load_memo(None)
        self.main_stack.set_visible_child_name('memo_edit')

    def _on_memo_clicked(self, memo):
        """Edit memo → edit screen"""
        self.memo_edit_view.load_memo(memo)
        self.main_stack.set_visible_child_name('memo_edit')

    def _on_back_clicked(self, button):
        """Back → memo list or search results"""
        if self._needs_reload:
            if self._search_query and self._search_results is not None:
                # Refresh search results
                self._perform_search_refresh()
            else:
                self._reload_memos()
            self._needs_reload = False

        # Restore search results if was searching
        if self._search_query and self._search_results is not None:
            self.memos_view.show_search_results(self._search_results, self._search_query)

        self.main_stack.set_visible_child_name('memos')

    def _perform_search_refresh(self):
        """Re-run current search"""
        if not self.api or not self._search_query:
            return

        def worker():
            success, memos, _ = self.api.search_memos(self._search_query)
            GLib.idle_add(self._on_search_refresh_complete, success, memos)

        threading.Thread(target=worker, daemon=True).start()

    def _on_search_refresh_complete(self, success, memos):
        """Handle search refresh"""
        if success:
            self._search_results = memos
            self.memos_view.show_search_results(memos, self._search_query)

    def _setup_actions(self):
        """Setup window actions"""
        prefs_action = Gio.SimpleAction.new("preferences", None)
        prefs_action.connect("activate", self._on_preferences)
        self.add_action(prefs_action)

        disconnect_action = Gio.SimpleAction.new("disconnect", None)
        disconnect_action.connect("activate", self._on_disconnect)
        disconnect_action.set_enabled(False)
        self.add_action(disconnect_action)
        self.disconnect_action = disconnect_action

    # -------------------------------------------------------------------------
    # SEARCH
    # -------------------------------------------------------------------------

    def _on_search_results(self, query, memos):
        """Handle search results"""
        self._search_query = query
        self._search_results = memos if query else None

        if query is None:
            self.memos_view.restore_all_memos()
        else:
            self.memos_view.show_search_results(memos, query)

    # -------------------------------------------------------------------------
    # SAVE / DELETE
    # -------------------------------------------------------------------------

    def _on_save_memo(self, memo, text, attachments, is_autosave=False):
        """Save or update memo"""
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
                        memo.get('name'), text, attachments, existing
                    )
                else:
                    success, result = self.api.update_memo(memo.get('name'), text)
            else:
                if attachments:
                    success, result = self.api.create_memo_with_attachments(text, attachments)
                else:
                    success, result = self.api.create_memo(text)

            GLib.idle_add(lambda: self._on_save_complete(success, result, is_autosave))

        threading.Thread(target=worker, daemon=True).start()

    def _on_save_complete(self, success, result, is_autosave):
        """Handle save completion"""
        self.memo_edit_view.on_save_complete(success, result if success else None)

        if success and not is_autosave:
            if self._search_query:
                self._perform_search_refresh()
            else:
                self._reload_memos()
            self.main_stack.set_visible_child_name('memos')

    def _on_delete_memo(self, memo):
        """Delete memo"""
        if not self.api or not memo:
            return

        def worker():
            success = self.api.delete_memo(memo.get('name'))
            GLib.idle_add(lambda: self._on_delete_complete(success))

        threading.Thread(target=worker, daemon=True).start()

    def _on_delete_complete(self, success):
        """Handle delete completion"""
        if success:
            self._reload_memos()
            self.main_stack.set_visible_child_name('memos')

    # -------------------------------------------------------------------------
    # RELOAD
    # -------------------------------------------------------------------------

    def _reload_memos(self):
        """Refresh memo list from API"""
        def worker():
            success, memos, page_token = self.api.get_memos()
            GLib.idle_add(lambda: self._on_reload_complete(success, memos, page_token))

        threading.Thread(target=worker, daemon=True).start()

    def _on_reload_complete(self, success, memos, page_token):
        """Handle reload completion"""
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
        """Open preferences window"""
        prefs = PreferencesWindow(self, on_credentials_changed=self._on_credentials_changed)
        prefs.present()

    def _on_credentials_changed(self):
        """Handle credential change from preferences"""
        self._try_auto_connect()

    def _try_auto_connect(self):
        """Auto-connect if credentials saved"""
        settings = Settings()
        url = settings.get_server_url()
        token = settings.get_api_token()

        if url and token:
            self.connection_view.url_entry.set_text(url)
            self.connection_view.token_entry.set_text(token)
            self.connection_view._on_connect(None)
