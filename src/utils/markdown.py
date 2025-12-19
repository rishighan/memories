# utils/markdown.py
# Reusable markdown utilities for rendering and parsing

import re


class MarkdownUtils:
    """Utilities for markdown rendering"""

    @staticmethod
    def to_pango_markup(text):
        """
        Convert markdown to Pango markup for display in labels.
        Used for previews and read-only text.
        """
        # Escape existing markup
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Bold: **text** or __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
        
        # Italic: *text* or _text_
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
        text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'<i>\1</i>', text)
        
        # Strikethrough: ~~text~~
        text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)
        
        # Code: `text`
        text = re.sub(r'`(.+?)`', r'<tt>\1</tt>', text)
        
        # Headers: remove # symbols but keep text bold
        text = re.sub(r'^#{1,6}\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)
        
        # Links: [text](url) -> show underlined text
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'<u>\1</u>', text)
        
        # List bullets: convert to •
        text = re.sub(r'^[\s]*[-*+]\s+', '• ', text, flags=re.MULTILINE)
        
        # Numbered lists: keep as is
        text = re.sub(r'^[\s]*(\d+)\.\s+', r'\1. ', text, flags=re.MULTILINE)
        
        return text

    @staticmethod
    def parse_line_style(line):
        """
        Parse a line and return its style type and any special data.
        Used for applying TextBuffer tags in editors.
        
        Returns: (style_type, data)
        - style_type: 'h1', 'h2', 'h3', 'quote', 'code_block', 'list_bullet', 'list_number', 'normal'
        - data: dict with additional info (e.g., marker position for lists)
        """
        if line.startswith("# "):
            return ("h1", {})
        elif line.startswith("## "):
            return ("h2", {})
        elif line.startswith("### "):
            return ("h3", {})
        elif line.startswith("> "):
            return ("quote", {})
        elif line.startswith("    ") or line.startswith("\t"):
            return ("code_block", {})
        elif m := re.match(r"^([\s]*\d+\.\s+)", line):
            return ("list_number", {"marker_len": len(m.group(1))})
        elif m := re.match(r"^([\s]*[-*+]\s+)", line):
            return ("list_bullet", {"marker_len": len(m.group(1))})
        else:
            return ("normal", {})

    @staticmethod
    def find_inline_patterns(line):
        """
        Find inline markdown patterns in a line.
        Used for applying TextBuffer tags in editors.
        
        Returns: list of (start, end, pattern_type) tuples
        """
        patterns = []
        
        # Bold: **text**
        for m in re.finditer(r'\*\*(.+?)\*\*', line):
            patterns.append((m.start(), m.end(), "bold"))
        
        # Italic: *text* (not part of **)
        for m in re.finditer(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', line):
            patterns.append((m.start(), m.end(), "italic"))
        
        # Italic: _text_
        for m in re.finditer(r'_(.+?)_', line):
            patterns.append((m.start(), m.end(), "italic"))
        
        # Code: `text`
        for m in re.finditer(r'`(.+?)`', line):
            patterns.append((m.start(), m.end(), "code"))
        
        # Strikethrough: ~~text~~
        for m in re.finditer(r'~~(.+?)~~', line):
            patterns.append((m.start(), m.end(), "strikethrough"))
        
        # Links: [text](url)
        for m in re.finditer(r'\[(.+?)\]\((.+?)\)', line):
            patterns.append((m.start(), m.end(), "link"))
        
        return patterns

    @staticmethod
    def should_apply_inline_patterns(line):
        """
        Check if inline patterns should be applied to this line.
        Block-level elements like headers and code blocks don't get inline styling.
        """
        return not line.startswith(("# ", "## ", "### ", "> ", "    ", "\t"))
