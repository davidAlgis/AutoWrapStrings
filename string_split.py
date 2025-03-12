import sublime
import sublime_plugin
import re

def get_literal_indent(text, pos):
    """
    Returns the full text from the beginning of the line up to pos.
    (Used only for single/double-quoted strings to compute available width.)
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

def replace_triple_quote(match, max_len, prefix, quote):
    """
    Processes a triple-quoted string literal.
    
    For triple-quoted strings we want to output either:
    
        {prefix}{quote}
        {line_indent + wrapped content lines}
        {line_indent}{quote}
    
    or, if the original literal did not have a newline immediately after the opening
    triple quotes, we output without adding an extra newline.
    
    Here, we check if the original content started with a newline. If it did, we preserve
    that behavior; otherwise, we output the wrapped content immediately after the opening quotes.
    """
    content_raw = match.group('content')
    has_leading_newline = content_raw.startswith("\n")
    # Remove any leading newline for wrapping if present.
    content_to_wrap = content_raw.lstrip("\n") if has_leading_newline else content_raw
    lines = content_to_wrap.splitlines()
    if not lines:
        return "{}{}{}".format(prefix, quote, quote)
    # Compute whitespace indent from the prefix (which here is used for extracting indent)
    line_indent_match = re.match(r'\s*', prefix)
    line_indent = line_indent_match.group(0) if line_indent_match else ""
    # Compute common indent from nonblank content lines.
    def leading_spaces(s):
        return len(s) - len(s.lstrip(" "))
    non_blank = [line for line in lines if line.strip()]
    common = min(leading_spaces(line) for line in non_blank) if non_blank else 0
    dedented_lines = [line[common:] if len(line) >= common else line for line in lines]
    # Allowed width for each wrapped content line is max_len minus the indent.
    allowed_width = max_len - len(line_indent)
    if all(len(line) <= allowed_width for line in dedented_lines):
        # If nothing needs wrapping, return the literal unchanged.
        return "{}{}{}{}".format(prefix, quote, content_raw, quote)
    new_lines = []
    for line in dedented_lines:
        if line.strip() == "":
            new_lines.append("")
        else:
            wrapped = wrap_single_line(line, allowed_width)
            new_lines.extend(wrapped)
    common_indent_str = " " * common
    new_content = "\n".join(line_indent + common_indent_str + l for l in new_lines)
    if has_leading_newline:
        # Preserve a newline after the opening quotes.
        return "{}{}\n{}\n{}{}".format(prefix, quote, new_content, line_indent, quote)
    else:
        # Do not add an extra newline after the opening quotes.
        return "{}{}{}{}".format(prefix, quote, new_content, quote)

def replace_string(match, max_len, literal_indent, prefix, quote):
    """
    Processes a string literal.
    
    For triple-quoted strings, it calls replace_triple_quote.
    For single/double-quoted strings, it splits the content into adjacent literals.
    """
    if len(quote) == 3:
        return replace_triple_quote(match, max_len, prefix, quote)
    else:
        # For single/double-quoted strings:
        line_indent_match = re.match(r'\s*', literal_indent)
        line_indent = line_indent_match.group(0) if line_indent_match else ""
        first_line_max = max_len - len(literal_indent) - 2  # subtracting the two quotes
        other_lines_max = max_len - len(line_indent) - 2
        content = match.group('content')
        wrapped_lines = []
        remaining = content
        if len(remaining) <= first_line_max and "\n" not in remaining:
            wrapped_lines.append(remaining)
        else:
            wrapped_lines.append(remaining[:first_line_max])
            remaining = remaining[first_line_max:]
            if remaining:
                wrapped_lines.extend(wrap_single_line(remaining, other_lines_max))
        literals = []
        # First literal uses literal_indent and prefix.
        literals.append("{}{}{}{}".format(prefix, quote, wrapped_lines[0], quote))
        # Subsequent literals use only the whitespace indent.
        for seg in wrapped_lines[1:]:
            literals.append("{}{}{}{}".format(line_indent, quote, seg, quote))
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
