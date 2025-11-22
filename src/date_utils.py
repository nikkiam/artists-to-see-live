"""Shared date and time utilities used across the project."""

# Standard day-of-week names in order (Monday = 0, Sunday = 6)
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Mapping from day abbreviation to weekday number (0-6)
DAY_TO_WEEKDAY = {name: i for i, name in enumerate(DAY_NAMES)}
