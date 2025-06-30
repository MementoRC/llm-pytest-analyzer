"""
Natural Language Query CLI for pytest-analyzer.
"""

import argparse

from rich.console import Console

from ..core.nlp.query_processor import NLQueryProcessor
from ..core.nlp.response_generator import NLResponseGenerator
from ..utils.settings import load_settings

console = Console()


def main():
    parser = argparse.ArgumentParser(
        prog="pytest-analyzer nl-query",
        description="Query pytest-analyzer using natural language.",
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="Natural language query to process (if omitted, enters interactive mode)",
    )
    parser.add_argument(
        "--autocomplete",
        type=str,
        help="Suggest autocompletions for a partial query",
    )
    args = parser.parse_args()

    settings = load_settings()
    processor = NLQueryProcessor(settings=settings)
    responder = NLResponseGenerator()

    if args.autocomplete:
        completions = processor.suggest_autocomplete(args.autocomplete)
        console.print("[bold green]Autocomplete suggestions:[/bold green]")
        for c in completions:
            console.print(f"  - {c}")
        return 0

    if args.query:
        query = " ".join(args.query)
        result = processor.process_query(query)
        console.print(responder.generate(result))
        return 0

    # Interactive mode
    console.print("[bold cyan]Pytest Analyzer NL Query Interactive Mode[/bold cyan]")
    while True:
        try:
            user_input = console.input("[bold blue]You:[/bold blue] ")
            if user_input.strip().lower() in {"exit", "quit"}:
                break
            result = processor.process_query(user_input)
            console.print(responder.generate(result))
        except (KeyboardInterrupt, EOFError):
            break
    return 0


if __name__ == "__main__":
    main()
