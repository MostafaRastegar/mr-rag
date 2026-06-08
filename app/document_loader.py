"""
Document loader for JSON scraper output.

This module reads JSON files produced by the web scraper and
extracts text content from them.
"""

import json
from pathlib import Path
from typing import List, Dict, Any


class DocumentLoader:
    """Loads documents from JSON scraper output files."""

    def load(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Load documents from a JSON file.

        Expected JSON format: a list of objects, each with at
        least a 'content' or 'text' field. Additional fields
        like 'title', 'url', 'source' are kept as metadata.

        Args:
            file_path: Path to the JSON file.

        Returns:
            A list of dicts with 'content' and 'metadata' keys.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = [data]

        documents = []
        for item in data:
            content = item.get("content") or item.get("text") or ""
            if not content:
                continue

            metadata = {k: v for k, v in item.items() if k not in ("content", "text")}
            documents.append({"content": content, "metadata": metadata})

        return documents