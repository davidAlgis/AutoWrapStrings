import re

import sublime
import sublime_plugin


def wrap_line(line, max_len):
    """
    Wrap a single line into pieces of at most max_len characters.
    If the line is short enough, returns it unchanged.
    """
    if len(line) <= max_len:
        return line
    # Break the line into chunks of length max_len.
    pieces = re.findall(f".{{1,{max_len}}}", line)
    return "\n".join(pieces)


def wrap_string_content(content, max_len):
    """
    Process the string content: split it on existing newlines and wrap each line.
    """
    lines = content.splitlines()
    wrapped_lines = [wrap_line(line, max_len) for line in lines]
    return "\n".join(wrapped_lines)


def replace_string(match, max_len):
    """
    Given a regex match for a string literal, return a new version where the
    content is wrapped so no line exceeds max_len characters.
    """
    prefix = match.group("prefix") or ""
    quote = match.group("quote")
    content = match.group("content")

    # Wrap the inner content.
    new_content = wrap_string_content(content, max_len)

    # If the original string was not triple quoted, convert it so that newlines are valid.
    if len(quote) == 3:
        new_quote = quote
    else:
        new_quote = '"""'

    return f"{prefix}{new_quote}{new_content}{new_quote}"


def process_text(text, max_len):
    """
    Find all Python string literals in the file and replace their contents with
    wrapped text, ensuring no line exceeds max_len characters.
    """
    # Regex pattern to match string literals with optional prefixes.
    pattern = r'(?P<prefix>[fFrRuUbB]*)(?P<quote>"""|\'\'\'|"|\')(?P<content>.*?)(?P=quote)'
    # Use DOTALL so that dot (.) matches newline characters.
    return re.sub(
        pattern, lambda m: replace_string(m, max_len), text, flags=re.DOTALL
    )


class AutoWrapOnSave(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        # Only process Python files (or adjust condition as needed)
        file_name = view.file_name() or ""
        if not file_name.endswith(".py"):
            return

        # Get entire file content.
        region = sublime.Region(0, view.size())
        original_text = view.substr(region)
        max_len = 79  # fixed max length

        # Process the text.
        new_text = process_text(original_text, max_len)

        # Only update the file if changes were made.
        if new_text != original_text:
            # Run the replace command to update the buffer.
            view.run_command("auto_wrap_replace", {"text": new_text})


class AutoWrapReplaceCommand(sublime_plugin.TextCommand):
    def run(self, edit, text):
        # Replace the entire file content with the new text.
        region = sublime.Region(0, self.view.size())
        self.view.replace(edit, region, text)
