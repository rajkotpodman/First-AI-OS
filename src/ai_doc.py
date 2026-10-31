#!/usr/bin/env python3
"""
ai_doc.py - Instant Offline Documentation & API Reference CLI
Author: Search Engine Architect & Developer Tooling Specialist

CLI Command: ai-doc <query> [--lang <lang>] [--symbol] [--limit <n>] [--json] [--full]
Provides instant, sub-millisecond keyword/FTS search across developer documentation
without needing an internet connection.
"""

import os
import sys
import json
import argparse
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from offline_docs_engine import OfflineDocsEngine
from index_docs import DocsIndexer

# ==============================================================================
# ANSI Color Palette
# ==============================================================================
class Colors:
    CYAN = "\033[1;36m"
    BLUE = "\033[1;34m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    MAGENTA = "\033[1;35m"
    RED = "\033[1;31m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def format_code_block(code: str, lang: str) -> str:
    """Renders a code block in green with line numbers."""
    lines = code.strip().splitlines()
    formatted = []
    for idx, line in enumerate(lines, 1):
        formatted.append(f"  {Colors.DIM}{idx:2d} |{Colors.RESET} {Colors.GREEN}{line}{Colors.RESET}")
    return "\n".join(formatted)


def display_symbol_signature(engine: OfflineDocsEngine, symbol: str, lang: Optional[str] = None, as_json: bool = False):
    """Displays exact API signature, parameter list, and example."""
    sig_res = engine.get_api_signature(symbol, language=lang)
    if not sig_res:
        # Fallback to search
        results = engine.search_docs(symbol, language=lang, limit=1)
        if results:
            display_search_results(results, as_json=as_json, full_view=True)
            return
        print(f"{Colors.RED}[!] Symbol '{symbol}' not found in offline documentation index.{Colors.RESET}")
        return

    if as_json:
        print(json.dumps(sig_res.to_dict(), indent=2))
        return

    print(f"\n{Colors.BOLD}{Colors.CYAN}=== AI OS OFFLINE API REFERENCE ==={Colors.RESET}")
    print(f"{Colors.BOLD}Symbol:{Colors.RESET}    {Colors.MAGENTA}{sig_res.symbol}{Colors.RESET} [{sig_res.language.upper()}]")
    if sig_res.signature:
        print(f"{Colors.BOLD}Signature:{Colors.RESET} {Colors.YELLOW}{sig_res.signature}{Colors.RESET}")
    if sig_res.return_type:
        print(f"{Colors.BOLD}Returns:{Colors.RESET}   {Colors.BLUE}{sig_res.return_type}{Colors.RESET}")

    if sig_res.parameters:
        print(f"\n{Colors.BOLD}Parameters:{Colors.RESET}")
        for p in sig_res.parameters:
            print(f"  • {p}")

    if sig_res.summary:
        print(f"\n{Colors.BOLD}Description:{Colors.RESET}")
        print(f"  {sig_res.summary}")

    if sig_res.code_example:
        print(f"\n{Colors.BOLD}Official Code Example:{Colors.RESET}")
        print(format_code_block(sig_res.code_example, sig_res.language))

    if sig_res.doc_path:
        print(f"\n{Colors.DIM}Reference: {sig_res.doc_path}{Colors.RESET}\n")


def display_search_results(results: list, as_json: bool = False, full_view: bool = False):
    """Renders formatted search results with snippets and rank."""
    if as_json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
        return

    if not results:
        print(f"{Colors.YELLOW}[!] No matching documentation found for your query.{Colors.RESET}")
        print(f"{Colors.DIM}Tip: Try searching with a generic keyword or use 'ai-doc --seed' to update the index.{Colors.RESET}")
        return

    print(f"\n{Colors.BOLD}{Colors.CYAN}=== AI OS DOC SEARCH: {len(results)} RESULT(S) FOUND ==={Colors.RESET}\n")

    for idx, r in enumerate(results, 1):
        print(f"{Colors.BOLD}{Colors.BLUE}[{idx}] {Colors.MAGENTA}{r.symbol}{Colors.RESET} {Colors.DIM}({r.language.upper()}/{r.category}){Colors.RESET} - {Colors.BOLD}{r.title}{Colors.RESET}")

        if r.signature:
            print(f"    {Colors.YELLOW}Signature:{Colors.RESET} {r.signature}")

        # Clean HTML tags in excerpt
        clean_excerpt = r.excerpt.replace("<b>", Colors.BOLD + Colors.YELLOW).replace("</b>", Colors.RESET)
        print(f"    {Colors.DIM}Excerpt:{Colors.RESET}   {clean_excerpt}")

        if r.snippet and (full_view or idx == 1):
            print(f"    {Colors.DIM}Example:{Colors.RESET}")
            print(format_code_block(r.snippet, r.language))

        if r.path:
            print(f"    {Colors.DIM}Path: {r.path}{Colors.RESET}")
        print()


def main():
    parser = argparse.ArgumentParser(
        prog="ai-doc",
        description="Instant Offline Developer Documentation & API Search Tool for AI OS"
    )
    parser.add_argument("query", nargs="*", help="Query keywords or API symbol to search")
    parser.add_argument("-l", "--lang", type=str, help="Filter by language (e.g. python, node, rust, linux, sqlite)")
    parser.add_argument("-s", "--symbol", action="store_true", help="Look up exact symbol signature and parameter spec")
    parser.add_argument("-n", "--limit", type=int, default=5, help="Maximum number of results to display (default: 5)")
    parser.add_argument("-j", "--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("-f", "--full", action="store_true", help="Show full code snippets and expanded descriptions")
    parser.add_argument("--stats", action="store_true", help="Show offline index statistics")
    parser.add_argument("--seed", action="store_true", help="Force re-seed default documentation sets")

    args = parser.parse_args()

    engine = OfflineDocsEngine()

    # Auto-seed if empty
    if engine.is_empty():
        indexer = DocsIndexer(engine)
        indexer.seed_default_documentation()

    if args.seed:
        indexer = DocsIndexer(engine)
        indexer.seed_default_documentation(force=True)
        return

    if args.stats:
        stats = engine.get_stats()
        langs = engine.list_supported_languages()
        if args.json:
            stats["languages"] = langs
            print(json.dumps(stats, indent=2))
        else:
            print(f"\n{Colors.BOLD}{Colors.CYAN}=== AI OS OFFLINE DOCUMENTATION STATS ==={Colors.RESET}")
            print(f"Database Location: {stats['db_path']}")
            print(f"Total Entries:     {stats['total_entries']}")
            print(f"Total Docsets:     {stats['total_docsets']}")
            print(f"Database Size:     {stats['db_size_mb']} MB")
            print(f"\n{Colors.BOLD}Indexed Languages:{Colors.RESET}")
            for l in langs:
                print(f"  • {Colors.YELLOW}{l['language'].upper()}{Colors.RESET}: {l['total_symbols']} symbols (Categories: {', '.join(l['categories'])})")
            print()
        return

    if not args.query:
        parser.print_help()
        sys.exit(0)

    query_str = " ".join(args.query).strip()

    if args.symbol:
        display_symbol_signature(engine, query_str, lang=args.lang, as_json=args.json)
    else:
        # Check if query matches a known symbol directly
        exact = engine.get_api_signature(query_str, language=args.lang)
        if exact and not args.json:
            display_symbol_signature(engine, query_str, lang=args.lang, as_json=args.json)
        else:
            results = engine.search_docs(query_str, language=args.lang, limit=args.limit)
            display_search_results(results, as_json=args.json, full_view=args.full)


if __name__ == "__main__":
    main()
