import sublime
import sublime_plugin
import re

def split_literal(content, allowed_len):
    """
    Split the content into pieces of at most allowed_len characters.
    This function preserves original newline boundaries by processing
    each line individually.
    """
    pieces = []
    for line in content.split("\n"):
        if line == "":
            pieces.append("")  # preserve empty lines
        else:
            parts = re.findall(".{1," + str(allowed_len) + "}", line)
            pieces.extend(parts)
    return pieces

def replace_string(match, max_len):
    """
    Given a regex match for a string literal, split its content into multiple
    string literals if needed so that, when combined with the prefix and quotes,
    no line exceeds max_len characters.
    """
    prefix = match.group('prefix') or ""
    quote = match.group('quote')
    content = match.group('content')
    
    # For output, use a one-character quote regardless of triple quoting.
    if len(quote) == 3:
        new_quote = quote[0]
    else:
        new_quote = quote

    # Compute allowed content length by subtracting prefix and two quotes.
    allowed_len = max_len - len(prefix) - 2

    # If the content fits on one line, return it unchanged.
    if len(content) <= allowed_len and "\n" not in content:
        return prefix + new_quote + content + new_quote

    # Otherwise, split the content into pieces that fit the allowed length.
    pieces = split_literal(content, allowed_len)
    # Build a new literal for each piece.
    new_literals = [prefix + new_quote + piece + new_quote for piece in pieces]
    # Join them with newlines; in Python, adjacent string literals are concatenated.
    return "\n".join(new_literals)

def process_text(text, max_len):
    """
    Find all Python string literals in the file and process them so that
    no line (including the quotes) exceeds max_len characters.
    """
    pattern = r'(?P<prefix>[fFrRuUbB]*)(?P<quote>"""|\'\'\'|"|\')(?P<content>.*?)(?P=quote)'
    return re.sub(pattern, lambda m: replace_string(m, max_len), text, flags=re.DOTALL)

class AutoWrapOnSave(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        # Only process Python files (adjust as needed).
        file_name = view.file_name() or ""
        if not file_name.endswith(".py"):
            return

        region = sublime.Region(0, view.size())
        original_text = view.substr(region)
        max_len = 79  # Fixed maximum column length.

        new_text = process_text(original_text, max_len)

        if new_text != original_text:
            view.run_command("auto_wrap_replace", {"text": new_text})
            sublime.status_message("Auto-wrap applied to string literals")
        else:
            sublime.status_message("No auto-wrap changes needed")

class AutoWrapReplaceCommand(sublime_plugin.TextCommand):
    def run(self, edit, text):
        region = sublime.Region(0, self.view.size())
        self.view.replace(edit, region, text)
