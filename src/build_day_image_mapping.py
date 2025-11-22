"""Build mapping of image URLs to day-of-week using Claude vision API."""

import base64
import json
import logging
import os
import sys
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Constants
OUTPUT_FILE = Path("output/day_image_mapping.json")
EXAMPLE_EMAILS_DIR = Path("example_emails")


def extract_image_urls(html_file: Path) -> list[str]:
    """
    Extract all unique image URLs from HTML file.

    Args:
        html_file: Path to HTML file

    Returns:
        List of unique image URLs
    """
    with open(html_file, encoding="utf-8") as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, "lxml")
    img_tags = soup.find_all("img")

    # Extract src attributes
    urls = []
    for img in img_tags:
        src = img.get("src", "")
        if src and src.startswith("http"):
            urls.append(src)

    logger.info("Extracted %d image URLs from %s", len(urls), html_file.name)
    return urls


def analyze_image_with_claude(image_url: str, api_key: str) -> str | None:
    """
    Use Claude vision API to extract day-of-week from image.

    Args:
        image_url: URL of image to analyze
        api_key: Anthropic API key

    Returns:
        Normalized day (e.g., "Fri", "Sat", "Sun") or None if not a day delimiter
    """
    try:
        # Fetch image
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        # Encode image to base64
        image_data = base64.standard_b64encode(response.content).decode("utf-8")

        # Determine media type
        content_type = response.headers.get("content-type", "image/png")

        # Call Claude vision API
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": content_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "This image may contain a day-of-week delimiter "
                                "(like FRIDAY, SATURDAY, SUNDAY, etc.). If it does, "
                                "respond with ONLY the three-letter abbreviation "
                                "(Mon, Tue, Wed, Thu, Fri, Sat, Sun). "
                                "If it does NOT contain a day-of-week, respond with ONLY: NONE"
                            ),
                        },
                    ],
                }
            ],
        )

        # Extract response
        response_text = message.content[0].text.strip()

        # Normalize response
        day_map = {
            "Mon": "Mon",
            "Tue": "Tue",
            "Wed": "Wed",
            "Thu": "Thu",
            "Fri": "Fri",
            "Sat": "Sat",
            "Sun": "Sun",
        }

        if response_text in day_map:
            logger.info("Image %s -> %s", image_url[-40:], response_text)
            return response_text

        logger.info("Image %s -> NOT A DAY DELIMITER", image_url[-40:])
        return None

    except requests.Timeout:
        logger.error("Timeout fetching image: %s", image_url)
        return None
    except requests.RequestException as e:
        logger.error("Failed to fetch image %s: %s", image_url, e)
        return None
    except Exception as e:
        logger.error("Failed to analyze image %s: %s", image_url, e)
        return None


def build_mapping(html_files: list[Path], api_key: str) -> dict[str, str]:
    """
    Build URL → day mapping from multiple email files.

    Args:
        html_files: List of HTML file paths
        api_key: Anthropic API key

    Returns:
        Dict mapping image URL to day name
    """
    # Extract all unique image URLs
    all_urls = set()
    for html_file in html_files:
        urls = extract_image_urls(html_file)
        all_urls.update(urls)

    logger.info("Found %d unique image URLs across all files", len(all_urls))

    # Analyze each image
    mapping = {}
    for i, url in enumerate(sorted(all_urls), start=1):
        logger.info("Analyzing image %d/%d", i, len(all_urls))
        day = analyze_image_with_claude(url, api_key)
        if day:
            mapping[url] = day

    logger.info("Found %d day delimiter images", len(mapping))
    return mapping


def main():
    """Build and save the image mapping."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("output/build_day_image_mapping.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Find all HTML files in example_emails/
    if not EXAMPLE_EMAILS_DIR.exists():
        logger.error("Directory not found: %s", EXAMPLE_EMAILS_DIR)
        sys.exit(1)

    html_files = list(EXAMPLE_EMAILS_DIR.glob("*.html"))
    if not html_files:
        logger.error("No HTML files found in %s", EXAMPLE_EMAILS_DIR)
        sys.exit(1)

    logger.info("Found %d HTML files to process", len(html_files))

    # Build mapping
    mapping = build_mapping(html_files, api_key)

    # Save to output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)

    logger.info("Saved mapping to %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()
