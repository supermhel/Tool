"""Server-side template import (JSON, YAML, CSV).

Parsing happens here, not in the browser: the client ships the raw text and
the server validates it with the same TemplateIn model as the JSON API.
DOCX is intentionally unsupported (heavy parser, larger attack surface).
"""

import csv
import io
import json
import re

import yaml

_ANCHORS = re.compile(r"(^|[\s\[{,:-])[&*][A-Za-z0-9_-]+")


class ImportError_(ValueError):
    pass


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "template"


def _from_csv(text: str, filename: str) -> dict:
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        raise ImportError_("CSV is empty.")
    first = [c.strip().lower() for c in rows[0]]
    has_header = bool({"id", "label", "max", "weight"} & set(first))
    header = first if has_header else ["id", "label", "max", "weight", "detail"]
    body = rows[1:] if has_header else rows
    criteria = []
    for i, r in enumerate(body, 1):
        obj = {h: (r[j].strip() if j < len(r) else "") for j, h in enumerate(header)}
        try:
            criteria.append({
                "id": obj.get("id") or f"c{i}",
                "label": obj.get("label") or obj.get("name") or f"Criterion {i}",
                "max": float(obj.get("max") or 10),
                "weight": float(obj.get("weight") or 1),
                "detail": obj.get("detail", ""),
            })
        except ValueError as exc:
            raise ImportError_(f"CSV row {i}: max and weight must be numbers.") from exc
    stem = re.sub(r"\.[^.]+$", "", filename)
    return {"id": _slug(stem), "name": stem[:80] or "Imported template", "criteria": criteria}


def parse_template(filename: str, content: str) -> dict:
    """Return a raw template dict (not yet validated); raise ImportError_ on bad input."""
    name = filename.lower()
    try:
        if name.endswith(".json"):
            data = json.loads(content)
        elif name.endswith((".yaml", ".yml")):
            if _ANCHORS.search(content):
                raise ImportError_("YAML anchors and aliases are not allowed.")
            data = yaml.safe_load(content)
        elif name.endswith(".csv"):
            data = _from_csv(content, filename)
        else:
            raise ImportError_("Unsupported file type; use .json, .yaml/.yml or .csv.")
    except ImportError_:
        raise
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ImportError_(f"Could not parse {filename}: {exc}") from exc
    except RecursionError:
        raise ImportError_("File is nested too deeply.") from None
    if not isinstance(data, dict) or not isinstance(data.get("criteria"), list):
        raise ImportError_("Template must be an object with a 'criteria' list.")
    if not all(isinstance(k, str) for k in data):
        raise ImportError_("Top-level keys must be text.")
    if not data.get("id") and data.get("name"):
        data["id"] = _slug(str(data["name"]))
    return data
