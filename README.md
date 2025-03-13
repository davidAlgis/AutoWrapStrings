# AutoWrapStrings

**AutoWrapStrings** is a Sublime Text package that automatically wraps long Python string literals to fit within a specified maximum line length. The plugin processes both single/double-quoted strings and triple‑quoted strings, adjusting the content to avoid exceeding the defined column width.

![](auto_wrap_example.gif)

> [!WARNING]  
> While **AutoWrapStrings** aims to reformat Python string literals accurately, it may contain edge cases where the wrapping does not behave as expected. Use with caution and consider reviewing changes after applying auto wrap.


## Installation

You only need to place the packages files in a folder named `AutoWrapStrings` in your Sublime Text Packages directory.

## Usage

- **Manual Wrapping:**  
  Open the Command Palette (via `Ctrl+Shift+P` or `Cmd+Shift+P` on macOS) and run the command **AutoWrap: Apply Auto Wrap to File** to manually trigger auto wrapping.

- **Auto-Wrap on Save:**  
  When you save a Python file, if the setting `apply_on_save` is enabled (default is disabled), the plugin will automatically reformat string literals to ensure no line exceeds the `max-line-length` (default is 79).

- **Configurable Settings:**  
  Customize the maximum line length and enable or disable auto-wrapping on save through the settings available in ``Preferences/Package Settings\AutoWrapStrings\Settings`.

