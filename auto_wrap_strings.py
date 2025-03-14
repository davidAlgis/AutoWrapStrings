"""Process string literals and comments for auto wrapping.

This module implements auto wrap functionality for Python string literals
and both standalone and inline comments in Sublime Text on file save.
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
        content = match.group("content")
        # If the content of a single/double-quoted literal spans multiple lines,
        # it likely isn't a valid literal (or is picked up from a comment).
        # In that case, leave it unchanged.
        if "\n" in content:
            return match.group(0)

        line_indent_match = re.match(r"\s*", literal_indent)
        line_indent = line_indent_match.group(0) if line_indent_match else ""
        first_line_max = max_len - len(literal_indent) - 2
        other_lines_max = max_len - len(line_indent) - 2

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
        # The first line always keeps the original prefix.
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


def wrap_comment_line(line, max_len):
    """
    Wrap a standalone comment line into multiple lines if it exceeds max_len.
    It preserves the indentation and '#' marker.
    """
    match = re.match(r"^(?P<indent>\s*#\s*)(?P<content>.*)$", line)
    if not match:
        return line
    indent = match.group("indent")
    content = match.group("content")
    available_width = max_len - len(indent)
    if available_width <= 0:
        return line
    wrapped_lines = textwrap.wrap(
        content,
        width=available_width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not wrapped_lines:
        return line
    return "\n".join(indent + l for l in wrapped_lines)


def wrap_inline_comment_line(line, max_len):
    """
    Wrap an inline comment (code followed by a comment) so that the comment text
    is split into a first part on the same line and subsequent lines starting
    with the same overall indentation and a '# ' marker.

    For example, given:
        platea = 0  # test if adding quote in comment result in some weird change himenaeos quis netus aene
    it returns:
        [
            "platea = 0  # test if adding quote in comment result in some weird change",
            "# himenaeos quis netus aene"
        ]
    or if the line is indented:
        "    platea = 0  # test if adding quote in comment result in some weird change himenaeos quis netus aene"
    it returns:
        [
            "    platea = 0  # test if adding quote in comment result in some weird change",
            "    # himenaeos quis netus aene"
        ]
    """
    m = re.match(r"^(?P<code>.*?)(?P<cm>\s*#\s+)(?P<comment>.+)$", line)
    if not m:
        return [line]
    code = m.group("code")
    cm = m.group("cm")
    comment = m.group("comment")

    # Get the overall leading whitespace from the entire line.
    leading_ws = re.match(r"^(\s*)", line).group(1)

    first_width = max_len - len(code) - len(cm)
    # For subsequent lines, we want the available width after the overall indentation and "# ".
    subsequent_width = max_len - len(leading_ws) - 2  # 2 for "# "
    if first_width < 1:
        return [line]

    # Manually fill the first line.
    words = comment.split()
    first_line_words = []
    current_len = 0
    while words:
        word = words[0]
        if not first_line_words:
            if len(word) <= first_width:
                first_line_words.append(word)
                current_len = len(word)
                words.pop(0)
            else:
                first_line_words.append(word)
                words.pop(0)
                break
        else:
            if current_len + 1 + len(word) <= first_width:
                first_line_words.append(word)
                current_len += 1 + len(word)
                words.pop(0)
            else:
                break
    first_line_text = " ".join(first_line_words)
    remaining_text = " ".join(words)
    subsequent_lines = (
        textwrap.wrap(
            remaining_text,
            width=subsequent_width,
            break_long_words=False,
            break_on_hyphens=False,
        )
        if remaining_text
        else []
    )
    result = []
    # The first line preserves the original code and inline comment marker.
    result.append("{}{}{}".format(code, cm, first_line_text))
    # Subsequent lines use the overall leading whitespace plus a standard "# " prefix.
    for l in subsequent_lines:
        result.append("{}# {}".format(leading_ws, l))
    return result


def process_comments(text, max_len):
    """
    Process the text to auto-wrap both standalone and inline comments.
    It splits the text into lines, checks for inline comments, wraps them,
    and then rejoins.
    """
    new_lines = []
    for line in text.splitlines():
        if "#" in line:
            m = re.match(r"^(?P<code>.*?)(\s*#\s+)(?P<comment>.+)$", line)
            if m:
                code = m.group("code")
                if code.strip() == "":
                    # Standalone comment.
                    wrapped = wrap_comment_line(line, max_len)
                    new_lines.extend(wrapped.splitlines())
                else:
                    # Inline comment.
                    wrapped_lines = wrap_inline_comment_line(line, max_len)
                    new_lines.extend(wrapped_lines)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


class AutoWrapOnSave(sublime_plugin.EventListener):
    """Listen for file save events and auto wrap string literals and comments."""

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
        new_text = process_comments(new_text, max_len)
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
    """Manually apply auto wrapping to string literals and comments."""

    def run(self, edit):
        """Apply auto wrapping to the current file."""
        settings = AutoWrapStringsSettings()
        max_len = settings.get("max-line-length", 79)
        region = sublime.Region(0, self.view.size())
        original_text = self.view.substr(region)
        new_text = process_text(original_text, max_len)
        new_text = process_comments(new_text, max_len)
        if new_text != original_text:
            self.view.run_command("auto_wrap_replace", {"text": new_text})
            sublime.status_message("Auto-wrap applied manually.")
        else:
            sublime.status_message("No auto-wrap needed.")
