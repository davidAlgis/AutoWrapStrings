"""Settings for AutoWrapString package."""

import sublime


class AutoWrapStringsSettings:
    """Load and manage AutoWrapStrings package settings."""

    def __init__(self, parent=None):
        """Initialize the settings loader."""
        self.parent = parent
        self.global_settings = sublime.load_settings(
            "AutoWrapStrings.sublime-" "settings"
        )

    def get(self, key, default=None):
        """Retrieve a setting value.

        First, check the view’s project settings under "AutoWrapStrings".
        Then, fall back to project data if available.
        Finally, return the global setting value.
        """
        window = sublime.active_window()
        view = window.active_view() if window else None

        # Try to get project-level settings from view settings
        project_settings = {}
        if view:
            project_settings = view.settings().get("AutoWrapStrings", {}) or {}
        if key in project_settings:
            return project_settings[key]

        # Fall back to old-style project data settings
        project_data = window.project_data() if window else {}
        if project_data and "AutoWrapStrings" in project_data:
            project_project_settings = project_data["AutoWrapStrings"]
            if key in project_project_settings:
                return project_project_settings.get(key)

        # Finally, return the global setting
        return self.global_settings.get(key, default)
