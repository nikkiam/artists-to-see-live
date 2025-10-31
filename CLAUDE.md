# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python 3.12 uv init based project for tracking artists to see live. The project is in early development stages.

## Development Environment

- **Python Version**: 3.12 (specified in `.python-version`)
- **Package Manager**: This project uses `pyproject.toml` for dependency management (created with `uv init`)
- **Virtual Environment**: `.venv` (gitignored)

## Project Structure

- `example_emails/`: Contains HTML email samples (likely concert/artist notifications that need parsing)
  - These emails appear to be the data source for the application
  - Email files are date-stamped (format: YYYY-MM-DD.html)

## Architecture Notes

The project appears designed to:
1. Parse HTML emails containing concert/artist information
2. Extract and track artist performance data

The example email in `example_emails/2025-10-31.html` is ~3800 lines of HTML table markup, suggesting the need for robust HTML parsing to extract structured data from concert notification emails.
