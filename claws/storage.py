"""
File output utilities: create directories and write Markdown files.
"""

import os


def ensure_output_dir(path):
    """Create directory tree if it doesn't exist."""
    dirpath = os.path.dirname(path)
    os.makedirs(dirpath, exist_ok=True)


def save_markdown(content, filepath):
    """
    Write Markdown content to a file with UTF-8 encoding.
    Creates parent directories automatically.
    """
    ensure_output_dir(filepath)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def save_file(content, filepath, encoding="utf-8"):
    """
    Write arbitrary content to a file.
    Creates parent directories automatically.
    """
    ensure_output_dir(filepath)
    with open(filepath, "w", encoding=encoding) as f:
        f.write(content)
