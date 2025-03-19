"""Settings for AutoWrapString package."""

import sublime


class AutoWrapStringsSettings:
    """Load and manage AutoWrapStrings package settings."""

    def __init__(self):
        """Initialize the settings loader."""
        self.global_settings = sublime.load_settings(
            "AutoWrapStrings.sublime-settings"
        )
        self._cached = None

        # Listen for changes in the global settings and clear the cache when
        # they change.
        self.global_settings.clear_on_change("auto_wrap_strings")
        self.global_settings.add_on_change(
            "auto_wrap_strings", self.clear_cache
        )

    def clear_cache(self):
        """Clear the cached merged settings."""
        self._cached = None

    def _get_merged_settings(self):
        """
        Merge global settings with view-level/project settings and cache the
        result.
        The precedence is as follows:
          1. Global settings are loaded first.
          2. View (or project) settings under the key "AutoWrapStrings"
        override global settings.
        """
        if self._cached is not None:
            return self._cached
        # Start with the global settings.
        merged = dict(self.global_settings)

        # Then override with view-level/project settings if available.
        window = sublime.active_window()
        if window:
            view = window.active_view()
            if view:
                project_settings = view.settings().get("AutoWrapStrings", {})
                merged.update(project_settings)
        self._cached = merged
        return merged

    def get(self, key, default=None):
        """Retrieve a setting value.

        The search order is:
          1. Check the view’s project settings under "AutoWrapStrings".
          2. Then fall back to project data if available.
          3. Finally, return the global setting value.

        :param key: The key of the setting to retrieve.
        :param default: The value to return if the key is not found.
        :return: The setting value.
        """
        return self._get_merged_settings().get(key, default)