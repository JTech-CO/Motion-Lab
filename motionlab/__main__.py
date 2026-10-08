"""Dependency-free Motion Lab CLI."""

import argparse
import csv
import io
import json
from pathlib import Path
import sqlite3
import sys

from .catalog import Catalog, CatalogUnavailable
from .mcp import run_stdio
from .server import serve
from .validation import CATEGORIES, KINDS, ValidationError
from .analysis_schema import ANALYSIS_FILTERS


def parser():
    root = argparse.ArgumentParser(description="Motion Lab motion code and reference library")
    root.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                      help="Project directory (default: installed package parent)")
    commands = root.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="Search motion code and references")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--category", choices=CATEGORIES, default="")
    search.add_argument("--license", default="")
    search.add_argument("--kind", choices=KINDS, default="")
    for field, allowed in ANALYSIS_FILTERS.items():
        search.add_argument("--" + field.replace("_", "-"), choices=allowed, default="")
    search.add_argument("--limit", type=int, default=24)
    search.add_argument("--offset", type=int, default=0)
    search.add_argument("--json", action="store_true")
    get = commands.add_parser("get", help="Get one catalog entry")
    get.add_argument("id")
    get.add_argument("--json", action="store_true")
    commands.add_parser("stats", help="Catalog counts as JSON")
    export = commands.add_parser("export", help="Export all public catalog entries")
    export.add_argument("--format", choices=("json", "csv"), default="json")
    export.add_argument("--output", type=Path)
    server = commands.add_parser("serve", help="Run the loopback web/API server")
    server.add_argument("--port", type=int, default=8787)
    server.add_argument("--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1")
    commands.add_parser("mcp", help="Run the read-only MCP stdio server")
    return root


def render_export(items, format_name):
    if format_name == "json":
        return json.dumps(items, ensure_ascii=False, indent=2) + "\n"
    stream = io.StringIO(newline="")
    fields = ("id", "title", "description", "category", "kind", "license", "sourceName", "sourceUrl", "tags", "colors", "analysis", "code")
    writer = csv.DictWriter(stream, fields, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        row = {key: item.get(key, "") for key in fields}
        for key in ("tags", "colors", "analysis"):
            row[key] = json.dumps(row[key], ensure_ascii=False)
        # Prevent spreadsheet formula execution when opening exported CSV.
        for key, value in row.items():
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                row[key] = "'" + value
        writer.writerow(row)
    return stream.getvalue()


def main(argv=None):
    options = parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    catalog = Catalog(options.root)
    try:
        if options.command == "mcp":
            run_stdio(catalog)
        elif options.command == "serve":
            if not 1 <= options.port <= 65535:
                raise ValidationError("port must be from 1 to 65535")
            serve(options.root, options.port, options.host)
        elif options.command == "search":
            result = catalog.search(query=options.query, category=options.category, license=options.license,
                                    kind=options.kind, limit=options.limit, offset=options.offset,
                                    **{field: getattr(options, field) for field in ANALYSIS_FILTERS})
            if options.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                for item in result["items"]:
                    print(f"{item['id']}  {item['title']}  [{item['category']} · {item['license']}]")
                print(f"{len(result['items'])} shown / {result['total']} matches")
        elif options.command == "get":
            item = catalog.get(options.id)
            if not item:
                print("Item not found", file=sys.stderr)
                return 1
            if options.json:
                print(json.dumps(item, ensure_ascii=False, indent=2))
            else:
                print(f"{item['title']} ({item['id']})\n{item['description']}\nLicense: {item['license']}\nSource: {item['sourceUrl']}")
                if item.get("code"):
                    print(item["code"])
        elif options.command == "stats":
            print(json.dumps(catalog.stats(), ensure_ascii=False, indent=2))
        elif options.command == "export":
            rendered = render_export(catalog.export(), options.format)
            if options.output:
                options.output.write_text(rendered, encoding="utf-8", newline="")
            else:
                sys.stdout.write(rendered)
        return 0
    except (ValidationError, CatalogUnavailable, OSError, sqlite3.Error) as error:
        print(f"Motion Lab: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
