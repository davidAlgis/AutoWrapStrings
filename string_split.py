import sublime
import sublime_plugin
import re

def get_line_indent(text, pos):
    """
    Find the indentation (leading whitespace) of the line at position pos.
    """
    line_start = text.rfind('\n', 0, pos) + 1
    line_end = line_start
    while line_end < len(text) and text[line_end] in (' ', '\t'):
        line_end += 1
    return text[line_start:line_end]

def wrap_single_line(text, max_len):
    """
    Split a single line into pieces of at most max_len characters.
    """
    return re.findall(".{1," + str(max_len) + "}", text)

def wrap_string_content(content, max_len):
    """
    Wrap each line in content separately.
    """
    lines = content.splitlines()
    wrapped_lines = []
    for line in lines:
        if line:
            wrapped_lines.extend(wrap_single_line(line, max_len))
        else:
            wrapped_lines.append('')
    return wrapped_lines

def replace_string(match, max_len, instruction_indent, prefix, quote):
    """
    Process a string literal so that the entire instruction's indentation is used
    for subsequent adjacent literals.
    """
    content = match.group('content')
    
    # Triple-quoted strings: preserve the triple quotes.
    if len(quote) == 3:
        inner_max_len = max_len - len(instruction_indent)
        wrapped_lines = wrap_string_content(content.strip("\n"), inner_max_len)
        inner_content = '\n'.join(instruction_indent + line for line in wrapped_lines)
        return "{}{}\n{}\n{}{}".format(prefix, quote, inner_content, instruction_indent, quote)
    
    # Single or double quoted strings:
    else:
        first_line_max_len = max_len - len(instruction_indent) - len(prefix) - 2  # subtract quotes and prefix
        other_lines_max_len = max_len - len(instruction_indent) - 2
        
        wrapped_lines = []
        remaining_content = content
        
        # Handle the first segment separately.
        if len(remaining_content) <= first_line_max_len:
            wrapped_lines.append(remaining_content)
            remaining_content = ''
        else:
            wrapped_lines.append(remaining_content[:first_line_max_len])
            remaining_content = remaining_content[first_line_max_len:]
        
        # Process remaining content.
        if remaining_content:
            wrapped_lines.extend(wrap_single_line(remaining_content, other_lines_max_len))
        
        # Build the final string literals.
        literals = []
        # First literal with prefix.
        literals.append("{}{}{}{}".format(prefix, quote, wrapped_lines[0], quote))
        # Subsequent literals with the instruction's indent.
        for line in wrapped_lines[1:]:
            literals.append("{}{}{}{}".format(instruction_indent, quote, line, quote))
        return "\n".join(literals)

def process_text(text, max_len):
    """
    Find and process all Python string literals in the file.
    """
    pattern = r'(?P<prefix>[fFrRuUbB]*)(?P<quote>"""|\'\'\'|"|\')(?P<content>.*?)(?P=quote)'
    
    def repl(match):
        prefix = match.group('prefix') or ''
        quote = match.group('quote')
        instruction_indent = get_line_indent(text, match.start())
        return replace_string(match, max_len, instruction_indent, prefix, quote)
    
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
