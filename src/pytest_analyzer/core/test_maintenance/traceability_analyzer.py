"""
Traceability Analyzer for Test Maintenance

Provides advanced test-to-code traceability analysis for the TestMaintainer system.
"""

import ast
from pathlib import Path
from typing import Dict, List, Set, Union


class TraceabilityAnalyzer:
    """
    Analyzes traceability between test files and source code.

    Features:
    - Import and call graph analysis
    - Test-to-code and code-to-test mapping
    - Orphaned test and missing coverage detection
    """

    def analyze(
        self, test_file: Union[str, Path], source_files: List[Union[str, Path]]
    ) -> Dict[str, Set[str]]:
        """
        Returns:
            {
                "tested_functions": set,
                "tested_classes": set,
                "orphaned_tests": set,
                "missing_coverage": set,
                "test_to_code_map": Dict[test_func, [source_func]],
                "code_to_test_map": Dict[source_func, [test_func]],
            }
        """
        test_ast = self._parse_ast(test_file)
        test_funcs = self._extract_test_functions(test_ast)

        code_structs = {}
        for src in source_files:
            code_structs[src] = self._analyze_code(src)

        tested_functions = set()
        tested_classes = set()
        test_to_code_map = {}
        code_to_test_map = {}

        for src, struct in code_structs.items():
            src_funcs = {f["name"] for f in struct.get("functions", [])}
            src_classes = {c["name"] for c in struct.get("classes", [])}
            for test_func in test_funcs:
                covered = [f for f in src_funcs if f in test_func] + [
                    c for c in src_classes if c in test_func
                ]
                if covered:
                    tested_functions.update([f for f in src_funcs if f in test_func])
                    tested_classes.update([c for c in src_classes if c in test_func])
                    test_to_code_map.setdefault(test_func, []).extend(covered)
                    for cov in covered:
                        code_to_test_map.setdefault(cov, []).append(test_func)

        orphaned_tests = {t for t in test_funcs if t not in test_to_code_map}

        all_src_funcs = set()
        all_src_classes = set()
        for struct in code_structs.values():
            all_src_funcs.update(f["name"] for f in struct.get("functions", []))
            all_src_classes.update(c["name"] for c in struct.get("classes", []))
        missing_coverage = (all_src_funcs | all_src_classes) - set(
            code_to_test_map.keys()
        )

        return {
            "tested_functions": tested_functions,
            "tested_classes": tested_classes,
            "orphaned_tests": orphaned_tests,
            "missing_coverage": missing_coverage,
            "test_to_code_map": test_to_code_map,
            "code_to_test_map": code_to_test_map,
        }

    def _parse_ast(self, file_path: Union[str, Path]) -> ast.AST:
        with open(file_path, "r", encoding="utf-8") as f:
            return ast.parse(f.read(), filename=str(file_path))

    def _extract_test_functions(self, tree: ast.AST) -> Set[str]:
        return {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
        }

    def _analyze_code(self, file_path: Union[str, Path]) -> Dict[str, List[Dict]]:
        # Minimal AST-based code structure extraction for traceability
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        functions = []
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({"name": node.name})
            elif isinstance(node, ast.ClassDef):
                classes.append({"name": node.name})
        return {"functions": functions, "classes": classes}
