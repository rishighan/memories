# Memories

A native GNOME client for [Memos](https://usememos.com/).

<p align="center">
  <img src="screenshots/login.png" width="49%" />
  <img src="screenshots/list.png" width="49%" />
</p>

## Features

- ✍️ **Full memo editing** - Create, edit, and delete memos with autosave
- 📎 **Attachments** - Drag-and-drop file uploads with visual management
- 🔍 **Search** - Fast full-text search across all memos
- 📅 **Activity heatmap** - GitHub-style calendar showing memo creation patterns
- 🎨 **Markdown styling** - Live syntax highlighting for headings, lists, code, links, and more
- 🏷️ **Metadata display** - View tags, pins, relations, reactions, and comments
- ♾️ **Infinite scroll** - Seamless pagination through large memo collections
- 🔐 **Bearer token auth** - Secure connection to your Memos instance
- 🎨 **Native GNOME design** - Built with GTK4 and libadwaita

## Building

```bash
flatpak-builder --user --install --force-clean build-dir org.quasars.memories.json
flatpak run org.quasars.memories
```

## Stack

Python • GTK4 • libadwaita • Flatpak

## License

GPL-3.0-or-later
