import re

import sublime
import sublime_plugin


def get_literal_indent(text, pos):
    """
    Returns the full text from the beginning of the line up to pos.
    (Used only for single/double-quoted strings to compute available width.)
    """
    line_start = text.rfind("\n", 0, pos) + 1
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
            wrapped_lines.append("")
    return wrapped_lines


def replace_triple_quote(match, max_len, prefix, quote):
    """
        Processes a triple-quoted string literal.

        For each line in the literal that exceeds max_len:
          1. If a following line exists, move words from the end of the line
             (one by one) to the beginning of the next line (keeping that
             line’s indentation) until the line's length is below max_len.
          2. If the current line is the last content line (i.e. the line before
             the closing quotes), insert a new line (with the same indentation
             as the current line) and move words there until the line's length
    is reduced below max_len.
        If no adjustments are needed, the literal is returned unchanged.
        When adjustments are made, the closing triple quotes are output with
        the same indentation as the last content line.


    """
    content_raw = match.group("content")
    has_leading_newline = content_raw.startswith("\n")
    # Remove any leading newline for processing if present.
    content_to_wrap = (
        content_raw.lstrip("\n") if has_leading_newline else content_raw
    )
    lines = content_to_wrap.splitlines()
    if not lines:
        return "{}{}{}".format(prefix, quote, quote)

    # Keep a copy of the original lines.
    original_lines = list(lines)

    def adjust_lines(lines, max_len):
        i = 0
        while i < len(lines):
            line = lines[i]
            # Process this line if it exceeds max_len.
            if len(line) > max_len:
                # If there is a next line, apply rule 1.
                if i < len(lines) - 1:
                    while len(line) > max_len:
                        last_space = line.rfind(" ")
                        if last_space == -1:
                            # Cannot break this line further.
                            break
                        # Remove the last word from the line.
                        last_word = line[last_space + 1 :]
                        line = line[:last_space].rstrip()
                        # Prepend the removed word to the next line.
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
                        # Update the working copy of line.
                        line = lines[i]
                else:
                    # Rule 2: This is the last line.
                    indent_match = re.match(r"\s*", line)
                    indent = indent_match.group(0) if indent_match else ""
                    # Insert a new line after the current one with the same indentation.
                    lines.insert(i + 1, indent)
                    while len(line) > max_len:
                        last_space = line.rfind(" ")
                        if last_space == -1:
                            break
                        last_word = line[last_space + 1 :]
                        line = line[:last_space].rstrip()
                        new_line = lines[i + 1]
                        # new_line already starts with indent.
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
    # If no adjustments were made, return the original literal unchanged.
    if original_lines == adjusted_lines:
        return match.group(0)
    new_content = "\n".join(adjusted_lines)
    if has_leading_newline:
        # Use the indentation from the last adjusted content line for closing quotes.
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
    """
    Processes a string literal.

    For triple-quoted strings, it calls replace_triple_quote.
    For single/double-quoted strings, it splits the content into adjacent
    literals.
    """
    if len(quote) == 3:
        # Temporarily leave triple-quoted strings unchanged.
        return replace_triple_quote(match, max_len, prefix, quote)
        # return match.group(0)
    else:
        # For single/double-quoted strings:
        line_indent_match = re.match(r"\s*", literal_indent)
        line_indent = line_indent_match.group(0) if line_indent_match else ""
        first_line_max = (
            max_len - len(literal_indent) - 2
        )  # subtracting the two quotes
        other_lines_max = max_len - len(line_indent) - 2
        content = match.group("content")
        wrapped_lines = []
        remaining = content
        if len(remaining) <= first_line_max and "\n" not in remaining:
            wrapped_lines.append(remaining)
        else:
            wrapped_lines.append(remaining[:first_line_max])
            remaining = remaining[first_line_max:]
            if remaining:
                wrapped_lines.extend(
                    wrap_single_line(remaining, other_lines_max)
                )
        literals = []
        # First literal uses literal_indent and prefix.
        literals.append(
            "{}{}{}{}".format(prefix, quote, wrapped_lines[0], quote)
        )
        # Subsequent literals use only the whitespace indent.
        for seg in wrapped_lines[1:]:
            literals.append("{}{}{}{}".format(line_indent, quote, seg, quote))
        return "\n".join(literals)


def process_text(text, max_len):
    """
    Finds all Python string literals in the file and processes them.
    Ignores raw strings entirely.
    """
    pattern = r'(?P<prefix>[fFrRuUbB]*)(?P<quote>"""|\'\'\'|"|\')(?P<content>(?:\\.|(?!(?P=quote)).)*)(?P=quote)'

    def repl(match):
        prefix = match.group("prefix") or ""
        # Skip raw literals immediately
        if "r" in prefix.lower():
            return match.group(0)
        quote = match.group("quote")
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
