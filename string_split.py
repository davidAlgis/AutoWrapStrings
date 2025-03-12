import sublime
import sublime_plugin
import re

def get_literal_indent(text, pos):
    """
    Returns the full text from the beginning of the line up to pos.
    """
    line_start = text.rfind('\n', 0, pos) + 1
    return text[line_start:pos]

def wrap_single_line(text, max_len):
    """
    Splits a single line of text into pieces of at most max_len characters.
    """
    return re.findall(".{1," + str(max_len) + "}", text)

def wrap_string_content(content, max_len):
    """
    Splits content (which may contain explicit newlines) into wrapped lines.
    """
    lines = content.splitlines()
    wrapped_lines = []
    for line in lines:
        if line:
            wrapped_lines.extend(wrap_single_line(line, max_len))
        else:
            wrapped_lines.append('')
    return wrapped_lines

def replace_string(match, max_len, literal_indent, prefix, quote):
    """
    Processes a string literal so that its wrapped replacement does not cause any
    line to exceed max_len characters.
    
    For both triple-quoted and single/double-quoted strings, the text before the literal 
    (literal_indent) is used only for calculating available width.
    
    For triple-quoted strings, the replacement is:
      {quote}
      {line_indent}{wrapped content lines}
      {line_indent}{quote}
      
    For single/double-quoted strings, the replacement is split into adjacent string literals,
    with the first literal using the full available width (based on literal_indent) and subsequent
    literals using only the whitespace indent.
    """
    content = match.group('content')
    # Extract only the whitespace indent (leading spaces) from literal_indent.
    line_indent_match = re.match(r'\s*', literal_indent)
    if line_indent_match:
        line_indent = line_indent_match.group(0)
    else:
        line_indent = ""
    
    if len(quote) == 3:
        # Triple-quoted strings: do not reinsert literal_indent.
        inner_max_len = max_len - len(line_indent)
        wrapped_lines = wrap_string_content(content.strip("\n"), inner_max_len)
        inner_content = "\n".join(line_indent + line for line in wrapped_lines)
        # Return only the triple-quoted literal (without duplicating the assignment text).
        return "{}\n{}\n{}{}".format(quote, inner_content, line_indent, quote)
    else:
        # Single/double-quoted strings:
        first_line_max_len = max_len - len(literal_indent) - 2  # subtracting the two quotes
        other_lines_max_len = max_len - len(line_indent) - 2
        
        wrapped_lines = []
        remaining = content
        if len(remaining) <= first_line_max_len and "\n" not in remaining:
            wrapped_lines.append(remaining)
        else:
            wrapped_lines.append(remaining[:first_line_max_len])
            remaining = remaining[first_line_max_len:]
            if remaining:
                wrapped_lines.extend(wrap_single_line(remaining, other_lines_max_len))
        
        literals = []
        # The first literal uses the prefix (which may be non-empty, e.g. for f-strings)
        literals.append("{}{}{}{}".format(prefix, quote, wrapped_lines[0], quote))
        # Subsequent literals are indented with only the whitespace indent.
        for seg in wrapped_lines[1:]:
            literals.append("{}{}{}{}".format(line_indent, quote, seg, quote))
        # Adjacent string literals in Python are automatically concatenated.
        return "\n".join(literals)

def process_text(text, max_len):
    """
    Finds all Python string literals in the file and processes them.
    """
    pattern = r'(?P<prefix>[fFrRuUbB]*)(?P<quote>"""|\'\'\'|"|\')(?P<content>.*?)(?P=quote)'
    
    def repl(match):
        prefix = match.group('prefix') or ''
        quote = match.group('quote')
        literal_indent = get_literal_indent(text, match.start())
        return replace_string(match, max_len, literal_indent, prefix, quote)
    
    return re.sub(pattern, repl, text, flags=re.DOTALL)

class AutoWrapOnSave(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        file_name = view.file_name() or ""
        if not file_name.endswith(".py"):
            return
        
        region = sublime.Region(0, view.size())
        original_text = view.substr(region)
        max_len = 79
        
        new_text = process_text(original_text, max_len)
        if new_text != original_text:
            view.run_command("auto_wrap_replace", {"text": new_text})
            sublime.status_message("Auto-wrap applied.")
        else:
            sublime.status_message("No auto-wrap needed.")

class AutoWrapReplaceCommand(sublime_plugin.TextCommand):
    def run(self, edit, text):
        region = sublime.Region(0, self.view.size())
        self.view.replace(edit, region, text)
