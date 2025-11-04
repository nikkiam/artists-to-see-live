# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python 3.12 uv init based project for tracking artists to see live. The project is in early development stages.

## Development Environment

- **Python Version**: 3.12 (specified in `.python-version`)
- **Package Manager**: This project uses `pyproject.toml` for dependency management (created with `uv init`)
- **Virtual Environment**: `.venv` (gitignored)
- **Linter/Formatter**: Ruff (configured in `ruff.toml`)

## Project Structure

- `example_emails/`: Contains HTML email samples (likely concert/artist notifications that need parsing)
  - These emails appear to be the data source for the application
  - Email files are date-stamped (format: YYYY-MM-DD.html)
- `src/`: Source code modules
- `tests/`: Test files
- `output/`: Generated output files and data

## Architecture Notes

The project appears designed to:
1. Parse HTML emails containing concert/artist information
2. Extract and track artist performance data

The example email in `example_emails/2025-10-31.html` is ~3800 lines of HTML table markup, suggesting the need for robust HTML parsing to extract structured data from concert notification emails.

## Coding Style Guidelines

### Functional Programming Style
- Prefer a **functional programming style** over object-oriented approaches
- Use **immutable dataclasses** (with `frozen=True`) for data structures that need to be passed between functions
- Functions should be pure when possible (no side effects)
- Avoid mutation of data structures

### Typed Dataclasses and Data Loading
- **Always use dataclasses** for structured data instead of raw dictionaries
- Parse JSON into typed dataclasses at load time using dedicated loader functions (see `src/data_loader.py`)
- Filter invalid/incomplete data during parsing, not during processing
- This approach:
  - Eliminates `.get()` calls throughout the codebase
  - Provides clear visibility into what data is actually loaded
  - Catches data issues early at the boundary
  - Makes the code more maintainable with type checking
- Example:
  ```python
  # Good: Load and filter at boundary
  artists_map = load_similar_artists_map(filepath)  # Returns dict[str, ArtistSimilarityData]
  # Now you can safely access: artist_data.similar_artists (no .get() needed)

  # Avoid: Passing raw JSON dicts around and checking everywhere
  raw_data = json.load(f)
  if raw_data.get("status") == "success":  # Repeated checks everywhere
  ```

### Early Exit Pattern
- Always use **early exit** style of coding
- Check for error conditions and edge cases at the start of functions
- Use guard clauses with early returns instead of deeply nested conditionals
- Example:
  ```python
  def process_data(data):
      # Early exits first
      if not data:
          return None
      if not validate(data):
          return None

      # Main logic after
      return transform(data)
  ```

### List Comprehensions and Functional Constructs
- **Prefer list/dict/set comprehensions** over for loops for filtering and mapping operations
- Use comprehensions for simple transformations; use regular loops for complex logic
- Filter data at load time, not in the middle of processing
- Example (good):
  ```python
  # Filter at load time
  valid_artists = [a for a in artists if a.status == "success"]

  # Use comprehensions for transformations
  artist_names = [artist.name for artist in valid_artists]
  artist_map = {a.name: a.id for a in valid_artists}
  ```
- Example (avoid):
  ```python
  # Don't filter mid-loop with .get() and status checks
  for artist in all_artists:
      if artist.get("status") != "success":
          continue
      # process artist...
  ```

### Logging
- **NEVER use `print()` statements** - Ruff is configured to enforce this (T201 rule)
- Always log to a file using a proper logging function (see `log()` in `src/music_map_scraper.py`)
- Logs should be committed to source control so we can review what happened during long-running processes
- This allows reviewing execution history when returning after being AFK

### Code Quality
- Follow all Ruff linting rules (see `ruff.toml`)
- Maintain zero linting errors and warnings
- Use type hints for function signatures
- Keep functions small and focused on a single responsibility
