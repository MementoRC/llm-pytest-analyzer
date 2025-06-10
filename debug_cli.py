#!/usr/bin/env python3

from pytest_analyzer.cli.analyzer_cli import setup_parser

parser = setup_parser()

test_cases = [
    ['test_path'],
    ['analyze', 'test_path'],
    ['mcp', 'start', '--stdio']
]

for i, args in enumerate(test_cases):
    print(f"\nTest case {i+1}: {args}")
    try:
        parsed = parser.parse_args(args)
        print(f"SUCCESS: {parsed}")
        print(f"Has func: {hasattr(parsed, 'func')}")
    except SystemExit as e:
        print(f"FAILED: SystemExit {e.code}")
    except Exception as e:
        print(f"ERROR: {e}")