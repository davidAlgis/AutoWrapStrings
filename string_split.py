import sublime
import sublime_plugin
import re

def wrap_line(line, allowed_len):
    """
    Wrap a single line into pieces of at most allowed_len characters.
    Returns the line unchanged if it already fits.
    """
    if len(line) <= allowed_len:
        return line
    pieces = re.findall(".{1," + str(allowed_len) + "}", line)
    return "\n".join(pieces)

def wrap_string_content(content, allowed_len):
    """
    Splits the content on existing newlines and wraps each line.
    """
    lines = content.splitlines()
    wrapped_lines = [wrap_line(line, allowed_len) for line in lines]
    return "\n".join(wrapped_lines)

def split_literal(content, allowed_len):
    """
    Split content into chunks of at most allowed_len characters.
    (Used only for non-triple quoted strings.)
    """
    pieces = []
    for line in content.split("\n"):
        if line == "":
            pieces.append("")
        else:
            parts = re.findall(".{1," + str(allowed_len) + "}", line)
            pieces.extend(parts)
    return pieces

def replace_string(match, max_len):
    """
    Process a string literal so that, including quotes, no line exceeds max_len.
    Triple-quoted strings are preserved with their triple quotes.
    """
    prefix = match.group('prefix') or ""
    quote = match.group('quote')
    content = match.group('content')
    
    if len(quote) == 3:
        # For triple-quoted strings, preserve the triple quotes.
        # Remove leading/trailing newlines for consistent wrapping.
        content = content.strip("\n")
        wrapped_content = wrap_string_content(content, max_len)
        # Place the triple quotes on separate lines.
        return prefix + quote + "\n" + wrapped_content + "\n" + quote
    else:
        # For single or double quoted strings,
        # subtract the length of the prefix and two quotes from max_len.
        allowed_len = max_len - len(prefix) - 2
        # If content is short and has no newlines, return it unchanged.
        if len(content) <= allowed_len and "\n" not in content:
            return prefix + quote + content + quote
        # Otherwise, split content into multiple adjacent string literals.
        pieces = split_literal(content, allowed_len)
        new_literals = [prefix + quote + piece + quote for piece in pieces]
        # In Python, adjacent string literals are concatenated.
        return "\n".join(new_literals)

def process_text(text, max_len):
    """
    Process all Python string literals in the file.
    """
    pattern = r'(?P<prefix>[fFrRuUbB]*)(?P<quote>"""|\'\'\'|"|\')(?P<content>.*?)(?P=quote)'
    return re.sub(pattern, lambda m: replace_string(m, max_len), text, flags=re.DOTALL)

class AutoWrapOnSave(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        file_name = view.file_name() or ""
        if not file_name.endswith(".py"):
            return
        
        region = sublime.Region(0, view.size())
        original_text = view.substr(region)
        max_len = 79  # fixed maximum column length
        
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
