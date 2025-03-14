"""Process string literals for auto wrapping.

This module implements auto wrap functionality for Python string literals
in Sublime Text on file save.
"""

import re
import textwrap

import sublime
import sublime_plugin

from .settings import AutoWrapStringsSettings


def get_literal_indent(text, pos):
    """Return the text from the start of the line up to pos.

    Used only for single/double-quoted strings to compute available width.
    """
    line_start = text.rfind("\n", 0, pos) + 1
    return text[line_start:pos]


def wrap_single_line(text, max_len):
    """Split a single line into pieces without breaking words."""
    return textwrap.wrap(
        text, width=max_len, break_long_words=False, break_on_hyphens=False
    )


def wrap_string_content(content, max_len):
    """Split content into wrapped lines.

    Process content that may contain explicit newlines.
    """
    lines = content.splitlines()
    wrapped_lines = []
    for line in lines:
        if line:
            wrapped_lines.extend(wrap_single_line(line, max_len))
        else:
            wrapped_lines.append("")
    return wrapped_lines


def replace_triple_quote(match, max_len, prefix, quote):
    """Process a triple-quoted string literal.

    For each line in the literal that exceeds max_len:
      1. If a following line exists, move words from the end of the line
         (one by one) to the beginning of the next line (keeping that
         line’s indentation) until the line's length is below max_len.
      2. If the current line is the last content line (i.e. the line before the
         closing quotes), insert a new line (with the same indentation as the
         current line) and move words there until the line's length is reduced
         below max_len.

    If no adjustments are needed, return the literal unchanged.
    When adjustments are made, output the closing triple quotes with the same
    indentation as the last content line.
    """
    content_raw = match.group("content")
    has_leading_newline = content_raw.startswith("\n")
    content_to_wrap = (
        content_raw.lstrip("\n") if has_leading_newline else content_raw
    )
    lines = content_to_wrap.splitlines()
    if not lines:
        return "{}{}{}".format(prefix, quote, quote)
    original_lines = list(lines)

    def adjust_lines(lines, max_len):
        i = 0
        while i < len(lines):
            line = lines[i]
            if len(line) > max_len:
                if i < len(lines) - 1:
                    while len(line) > max_len:
                        last_space = line.rfind(" ")
                        if last_space == -1:
                            break
                        last_word = line[last_space + 1 :]
                        line = line[:last_space].rstrip()
                        next_line = lines[i + 1]
                        indent_match = re.match(r"\s*", next_line)
                        indent = indent_match.group(0) if indent_match else ""
                        next_line_content = next_line.lstrip()
                        if next_line_content:
                            new_next = (
                                indent + last_word + " " + next_line_content
                            )
                        else:
                            new_next = indent + last_word
                        lines[i] = line
                        lines[i + 1] = new_next
                        line = lines[i]
                else:
                    indent_match = re.match(r"\s*", line)
                    indent = indent_match.group(0) if indent_match else ""
                    lines.insert(i + 1, indent)
                    while len(line) > max_len:
                        last_space = line.rfind(" ")
                        if last_space == -1:
                            break
                        last_word = line[last_space + 1 :]
                        line = line[:last_space].rstrip()
                        new_line = lines[i + 1]
                        new_line_content = (
                            new_line[len(indent) :]
                            if new_line.startswith(indent)
                            else new_line
                        )
                        if new_line_content:
                            new_line = (
                                indent + last_word + " " + new_line_content
                            )
                        else:
                            new_line = indent + last_word
                        lines[i] = line
                        lines[i + 1] = new_line
                        line = lines[i]
            i += 1
        return lines

    adjusted_lines = adjust_lines(lines, max_len)
    if original_lines == adjusted_lines:
        return match.group(0)
    new_content = "\n".join(adjusted_lines)
    if has_leading_newline:
        closing_indent_match = re.match(r"\s*", adjusted_lines[-1])
        closing_indent = (
            closing_indent_match.group(0) if closing_indent_match else ""
        )
        return "{}{}\n{}\n{}{}".format(
            prefix, quote, new_content, closing_indent, quote
        )
    else:
        return "{}{}{}{}".format(prefix, quote, new_content, quote)


def replace_string(match, max_len, literal_indent, prefix, quote):
    """Process a string literal.

    For triple-quoted strings, call replace_triple_quote.
    For single/double-quoted strings, split the content into adjacent literals.
    """
    if len(quote) == 3:
        return replace_triple_quote(match, max_len, prefix, quote)
    else:
        line_indent_match = re.match(r"\s*", literal_indent)
        line_indent = line_indent_match.group(0) if line_indent_match else ""
        first_line_max = max_len - len(literal_indent) - 2
        other_lines_max = max_len - len(line_indent) - 2
        content = match.group("content")

        wrapped_lines = []
        remaining = content

        initial_wrap = wrap_single_line(remaining, first_line_max)
        if initial_wrap:
            wrapped_lines.append(initial_wrap[0])
            remaining = remaining[len(initial_wrap[0]) :].lstrip()
            if remaining:
                wrapped_lines.extend(
                    wrap_single_line(remaining, other_lines_max)
                )
        else:
            wrapped_lines.append("")

        literals = []
        # The first line always starts with the original prefix.
        literals.append(
            "{}{}{}{}".format(prefix, quote, wrapped_lines[0], quote)
        )
        # For subsequent lines, if it's an f-string, include the prefix.
        for seg in wrapped_lines[1:]:
            additional_prefix = prefix if "f" in prefix.lower() else ""
            literals.append(
                "{}{}{}{}{}".format(
                    line_indent, additional_prefix, quote, seg, quote
                )
            )
        return "\n".join(literals)


def process_text(text, max_len):
    """Find all Python string literals and process them.

    Ignore raw strings entirely.
    """
    pattern = (
        r'(?P<prefix>[fFrRuUbB]*)(?P<quote>"""|\'\'\'|"|\')'
        r"(?P<content>(?:\\.|(?!(?P=quote)).)*)(?P=quote)"
    )

    def repl(match):
        prefix = match.group("prefix") or ""
        if "r" in prefix.lower():
            return match.group(0)
        quote = match.group("quote")
        literal_indent = get_literal_indent(text, match.start())
        return replace_string(match, max_len, literal_indent, prefix, quote)

    return re.sub(pattern, repl, text, flags=re.DOTALL)


class AutoWrapOnSave(sublime_plugin.EventListener):
    """Listen for file save events and auto wrap string literals."""

    def on_pre_save(self, view):
        """Handle the pre-save event to apply auto-wrap to Python files."""
        settings = AutoWrapStringsSettings()
        if not settings.get("apply_on_save", False):
            return
        file_name = view.file_name() or ""
        if not file_name.endswith(".py"):
            return
        region = sublime.Region(0, view.size())
        original_text = view.substr(region)
        max_len = settings.get("max-line-length", 79)
        new_text = process_text(original_text, max_len)
        if new_text != original_text:
            view.run_command("auto_wrap_replace", {"text": new_text})
            sublime.status_message("Auto-wrap applied.")
        else:
            sublime.status_message("No auto-wrap needed.")


class AutoWrapReplaceCommand(sublime_plugin.TextCommand):
    """Replace the entire file content with auto wrapped text."""

    def run(self, edit, text):
        """Replace the file's content with auto wrapped text."""
        region = sublime.Region(0, self.view.size())
        self.view.replace(edit, region, text)


class AutoWrapApplyCommand(sublime_plugin.TextCommand):
    """Manually apply auto wrapping to string literals."""

    def run(self, edit):
        """Apply auto wrapping to the current file."""
        settings = AutoWrapStringsSettings()
        max_len = settings.get("max-line-length", 79)
        region = sublime.Region(0, self.view.size())
        original_text = self.view.substr(region)
        new_text = process_text(original_text, max_len)
        if new_text != original_text:
            self.view.run_command("auto_wrap_replace", {"text": new_text})
            sublime.status_message("Auto-wrap applied manually.")
        else:
            sublime.status_message("No auto-wrap needed.")
