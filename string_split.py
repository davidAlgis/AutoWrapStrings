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
    
    For triple-quoted strings, we want to output:
      {prefix}{quote}
      {line_indent + wrapped content lines}
      {line_indent}{quote}
    where line_indent is the whitespace indent of the literal’s opening line.
    (The assignment text preceding the literal is not reinserted.)
    """
    content = match.group('content')
    lines = content.splitlines()
    if not lines:
        return "{}{}{}".format(prefix, quote, quote)
    
    # Compute the whitespace indent from the start of the literal.
    # (Since the match does not include the assignment text, we use the prefix to extract indent.)
    line_indent_match = re.match(r'\s*', prefix)
    if line_indent_match:
        line_indent = line_indent_match.group(0)
    else:
        line_indent = ""
    
    # Compute common indent of nonblank content lines.
    def leading_spaces(s):
        return len(s) - len(s.lstrip(" "))
    non_blank = [line for line in lines if line.strip()]
    common = min(leading_spaces(line) for line in non_blank) if non_blank else 0
    dedented_lines = [line[common:] if len(line) >= common else line for line in lines]
    
    # Allowed width for content lines is max_len minus the whitespace indent.
    allowed_width = max_len - len(line_indent)
    
    # If all dedented lines already fit, return the literal unchanged.
    if all(len(line) <= allowed_width for line in dedented_lines):
        return "{}{}{}{}".format(prefix, quote, content, quote)
    
    # Otherwise, rewrap each dedented line.
    new_lines = []
    for line in dedented_lines:
        if line.strip() == "":
            new_lines.append("")
        else:
            wrapped = wrap_single_line(line, allowed_width)
            new_lines.extend(wrapped)
    # Re-add the common indent that was removed.
    common_indent_str = " " * common
    new_content = "\n".join(line_indent + common_indent_str + l for l in new_lines)
    
    # Build the final triple-quoted literal.
    return "{}{}\n{}\n{}{}".format(prefix, quote, new_content, line_indent, quote)

def replace_string(match, max_len, literal_indent, prefix, quote):
    """
    Processes a string literal.
    
    For triple-quoted strings, calls replace_triple_quote (ignoring literal_indent).
    For single/double-quoted strings, splits the content into adjacent literals using
    literal_indent to compute available width.
    """
    if len(quote) == 3:
        return replace_triple_quote(match, max_len, prefix, quote)
    else:
        # For single/double-quoted strings:
        line_indent_match = re.match(r'\s*', literal_indent)
        if line_indent_match:
            line_indent = line_indent_match.group(0)
        else:
            line_indent = ""
        first_line_max = max_len - len(literal_indent) - 2  # subtract the two quotes
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
