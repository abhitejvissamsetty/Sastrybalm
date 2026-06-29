import csv
import io
from typing import Generator


def parse_csv_bytes(content: bytes) -> list[dict]:
    """Parse UTF-8 (or UTF-8-BOM) CSV bytes into a list of row dicts."""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        cleaned = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
        if any(cleaned.values()):   # skip blank rows
            rows.append(cleaned)
    return rows
