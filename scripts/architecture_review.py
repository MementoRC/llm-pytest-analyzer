#!/usr/bin/env python3
"""
Architecture Review Script for pytest-analyzer.

This script performs a comprehensive architectural analysis of the pytest-analyzer
codebase. It is designed to be run from the root of the project repository.

It performs the following actions:
1.  Dependency Analysis: Uses `pydeps` to generate a module dependency graph.
    If `pydeps` is unavailable, it falls back to a manual AST-based analysis
    to calculate fan-in/fan-out for each module to assess coupling.
2.  Circular Dependency Detection: Analyzes the dependency graph to identify
    any circular import cycles, which are detrimental to maintainability.
3.  Interface & Contract Review: Uses Python's `ast` module to find all
    defined `Protocol` classes, assessing adherence to SOLID principles.
4.  Maintainability Metrics: Uses `radon` to calculate Cyclomatic Complexity
    and the Maintainability Index for all modules, highlighting areas of
    potential concern.
5.  Report Generation: Compiles all findings into a detailed Markdown report
    (`architecture_report.md`) with actionable recommendations.

Prerequisites:
- Python 3.8+
- `radon` installed (`pip install radon`)
- `pydeps` (optional, for more accurate dependency analysis) (`pip install pydeps`)

Usage:
    python scripts/architecture_review.py
"""

import ast
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Configuration ---
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src" / "pytest_analyzer"
REPORT_PATH = ROOT_DIR / "architecture_report.md"
PACKAGE_NAME = "pytest_analyzer"

# Temporary files for tool outputs
PYDEPS_OUTPUT_FILE = ROOT_DIR / "pydeps_report.json"
RADON_CC_REPORT_FILE = ROOT_DIR / "radon_cc_report.json"
RADON_MI_REPORT_FILE = ROOT_DIR / "radon_mi_report.json"
TEMP_FILES = [PYDEPS_OUTPUT_FILE, RADON_CC_REPORT_FILE, RADON_MI_REPORT_FILE]

# Thresholds for reporting
MAINTAINABILITY_INDEX_THRESHOLD = 40  # Grade B or below (Radon: A=100-20, B=19-10, C=9-0)
CYCLOMATIC_COMPLEXITY_THRESHOLD = 10  # High complexity (Rank D)
PROTOCOL_METHOD_THRESHOLD = 7  # For checking "fat" interfaces


# --- Helper Functions ---

def check_tool_installed(tool_name: str) -> bool:
    """Check if a command-line tool is installed and in the PATH."""
    if shutil.which(tool_name) is None:
        print(f"Info: '{tool_name}' is not installed or not in your PATH.")
        return False
    return True


def run_command(command: str, cwd: Path) -> bool:
    """Run a shell command and return True on success."""
    try:
        subprocess.run(
            command,
            shell=True,
            check=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}\n{e.stderr}")
        return False
    except FileNotFoundError:
        print(f"Error: Command not found for: {command}")
        return False


# --- Manual Dependency Analysis (AST-based) ---

class ImportVisitor(ast.NodeVisitor):
    """AST visitor to find all internal package imports."""

    def __init__(self, module_path: Path, src_root: Path, package_name: str):
        self.imports = set()
        self._module_path = module_path
        self._src_root = src_root
        self._package_name = package_name

        module_rel_path = self._module_path.relative_to(self._src_root)
        if module_rel_path.name == "__init__.py":
            module_rel_path = module_rel_path.parent
        else:
            module_rel_path = module_rel_path.with_suffix("")
        
        self._current_module_str = f"{package_name}." + ".".join(module_rel_path.parts[1:])


    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name.startswith(f"{self._package_name}."):
                self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module and node.module.startswith(f"{self._package_name}."):
            self.imports.add(node.module)
        elif node.level > 0:  # Relative import
            path_parts = self._current_module_str.split('.')
            
            if self._module_path.name == "__init__.py":
                base_path_parts = path_parts
            else:
                base_path_parts = path_parts[:-1]

            level = node.level
            if len(base_path_parts) < level - 1:
                return

            relative_base = base_path_parts[:len(base_path_parts) - (level - 1)]
            
            full_module_path_parts = relative_base
            if node.module:
                full_module_path_parts.extend(node.module.split('.'))
            
            full_module_path = ".".join(full_module_path_parts)
            if full_module_path.startswith(self._package_name):
                self.imports.add(full_module_path)
        self.generic_visit(node)


def analyze_dependencies_manually() -> Optional[Dict[str, Any]]:
    """Generates a dependency graph by parsing AST trees."""
    graph = defaultdict(list)
    module_info = {}

    py_files = list(SRC_DIR.rglob("*.py"))
    for py_file in py_files:
        module_rel_path = py_file.relative_to(SRC_DIR.parent)
        module_name = str(module_rel_path.with_suffix("").as_posix()).replace("/", ".")
        
        module_info[module_name] = {"path": str(py_file), "fan_out": 0, "fan_in": 0}

        try:
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
            visitor = ImportVisitor(py_file, SRC_DIR.parent, PACKAGE_NAME)
            visitor.visit(tree)
            
            dependencies = sorted(list(visitor.imports))
            graph[module_name] = dependencies
            module_info[module_name]["fan_out"] = len(dependencies)
        except Exception as e:
            print(f"Warning: Could not parse {py_file} for manual dependency analysis: {e}")

    for _, dependencies in graph.items():
        for dep in dependencies:
            if dep in module_info:
                module_info[dep]["fan_in"] += 1
    
    return {"graph": graph, "info": module_info, "source": "manual (AST)"}


# --- Analysis Sections ---

def analyze_dependencies() -> Optional[Dict[str, Any]]:
    """Generates and parses a dependency graph using pydeps or manual AST parsing."""
    print("1. Analyzing module dependencies...")
    if check_tool_installed("pydeps"):
        print("   ...using pydeps for high-accuracy analysis (this may take a moment)...")
        command = f"pydeps {SRC_DIR} --json --no-output > {PYDEPS_OUTPUT_FILE}"
        if run_command(command, ROOT_DIR):
            if PYDEPS_OUTPUT_FILE.exists() and PYDEPS_OUTPUT_FILE.stat().st_size > 0:
                with open(PYDEPS_OUTPUT_FILE, "r", encoding="utf-8") as f:
                    try:
                        pydeps_data = json.load(f)
                        graph = defaultdict(list)
                        module_info = {}

                        for details in pydeps_data.get("modules", []):
                            module_name = details["name"]
                            if not module_name.startswith(PACKAGE_NAME):
                                continue

                            module_info[module_name] = {"path": details.get("path"), "fan_out": 0, "fan_in": 0}
                            
                            dependencies = []
                            if details.get("imports"):
                                for imp in details["imports"]:
                                    if imp.startswith(PACKAGE_NAME):
                                        dependencies.append(imp)
                            
                            graph[module_name] = sorted(list(set(dependencies)))
                            module_info[module_name]["fan_out"] = len(dependencies)

                        for _, dependencies in graph.items():
                            for dep in dependencies:
                                if dep in module_info:
                                    module_info[dep]["fan_in"] += 1
                        
                        print("   ...pydeps analysis complete.")
                        return {"graph": graph, "info": module_info, "source": "pydeps"}
                    except json.JSONDecodeError:
                        print("Warning: Failed to parse pydeps JSON output. Falling back to manual analysis.")
            else:
                print("Warning: pydeps did not generate a valid output file. Falling back to manual analysis.")
        else:
            print("Warning: pydeps command failed. Falling back to manual analysis.")

    print("   ...pydeps not available or failed. Using manual AST-based analysis.")
    return analyze_dependencies_manually()


def find_circular_dependencies(graph: Dict[str, List[str]]) -> List[List[str]]:
    """Finds cycles in a directed graph using DFS."""
    print("2. Checking for circular dependencies...")
    cycles = []
    visiting: Set[str] = set()
    visited: Set[str] = set()

    for node in sorted(graph.keys()):
        if node not in visited:
            path: List[str] = []
            _find_cycles_util(node, graph, visiting, visited, path, cycles)

    unique_cycles = []
    seen_cycles: Set[Tuple[str, ...]] = set()
    for cycle in cycles:
        sorted_cycle = tuple(sorted(cycle))
        if sorted_cycle not in seen_cycles:
            unique_cycles.append(cycle + [cycle[0]])
            seen_cycles.add(sorted_cycle)

    print(f"   ...found {len(unique_cycles)} circular dependency groups.")
    return unique_cycles


def _find_cycles_util(
    node: str,
    graph: Dict[str, List[str]],
    visiting: Set[str],
    visited: Set[str],
    path: List[str],
    cycles: List[List[str]],
):
    visiting.add(node)
    path.append(node)

    for neighbor in graph.get(node, []):
        if neighbor in visiting:
            try:
                cycle_start_index = path.index(neighbor)
                cycles.append(path[cycle_start_index:])
            except ValueError:
                pass
        elif neighbor not in visited:
            _find_cycles_util(neighbor, graph, visiting, visited, path, cycles)

    path.pop()
    visiting.remove(node)
    visited.add(node)


class ProtocolVisitor(ast.NodeVisitor):
    """AST visitor to find Protocol definitions and their methods."""

    def __init__(self, file_path: Path):
        self.protocols: Dict[str, Dict[str, Any]] = {}
        self._file_path = file_path

    def visit_ClassDef(self, node: ast.ClassDef):
        is_protocol = False
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "Protocol":
                is_protocol = True
                break
            if (
                isinstance(base, ast.Attribute)
                and isinstance(base.value, ast.Name)
                and base.value.id in ("typing", "Protocol")
                and base.attr == "Protocol"
            ):
                is_protocol = True
                break

        if is_protocol:
            methods = [item.name for item in node.body if isinstance(item, ast.FunctionDef) and not item.name.startswith("_")]
            self.protocols[node.name] = {
                "methods": methods,
                "path": str(self._file_path.relative_to(ROOT_DIR)),
            }
        self.generic_visit(node)


def analyze_interfaces_and_contracts() -> Dict[str, Any]:
    """Finds all Protocol definitions in the codebase using AST."""
    print("3. Reviewing interface contracts (Protocols)...")
    all_protocols = {}
    for py_file in sorted(SRC_DIR.rglob("*.py")):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
            visitor = ProtocolVisitor(py_file)
            visitor.visit(tree)
            all_protocols.update(visitor.protocols)
        except Exception as e:
            print(f"Warning: Could not parse {py_file}: {e}")

    print(f"   ...found {len(all_protocols)} Protocol definitions.")
    return {"protocols": all_protocols}


def analyze_maintainability() -> Optional[Dict[str, Any]]:
    """Calculates maintainability metrics using radon."""
    print("4. Generating maintainability metrics with radon...")
    if not check_tool_installed("radon"):
        return None

    cc_command = f"radon cc -j -a {SRC_DIR} > {RADON_CC_REPORT_FILE}"
    mi_command = f"radon mi -j -s {SRC_DIR} > {RADON_MI_REPORT_FILE}"

    if not run_command(cc_command, ROOT_DIR) or not run_command(mi_command, ROOT_DIR):
        return None

    try:
        with open(RADON_CC_REPORT_FILE, "r", encoding="utf-8") as f:
            cc_data = json.load(f)
        with open(RADON_MI_REPORT_FILE, "r", encoding="utf-8") as f:
            mi_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading radon output: {e}")
        return None

    print("   ...maintainability analysis complete.")
    return {"cc": cc_data, "mi": mi_data}


# --- Report Generation ---

def generate_report(
    dep_analysis: Optional[Dict[str, Any]],
    circular_deps: List[List[str]],
    interface_analysis: Dict[str, Any],
    maintainability_analysis: Optional[Dict[str, Any]],
) -> str:
    """Generates a Markdown report from all analysis results."""
    print("5. Generating architecture report...")
    report_parts = ["# Pytest-Analyzer Architecture Review\n"]

    # --- Executive Summary ---
    report_parts.append("## 1. Executive Summary\n")
    summary = """
This report provides an automated analysis of the `pytest-analyzer` codebase architecture.
It covers module dependencies, circular references, interface design, and code maintainability.
The goal is to identify architectural strengths, weaknesses, and provide actionable
recommendations for improvement.
"""
    report_parts.append(summary)

    # --- Dependency Analysis ---
    report_parts.append("## 2. Dependency Analysis\n")
    if dep_analysis:
        info = dep_analysis["info"]
        num_modules = len(info)
        report_parts.append(f"Analyzed **{num_modules}** modules inside `src/pytest_analyzer` using **{dep_analysis['source']}**.\n")

        top_fan_out = sorted(info.items(), key=lambda item: item[1]["fan_out"], reverse=True)[:5]
        report_parts.append("### Highest Fan-Out (Most Coupled Modules)\n")
        report_parts.append("| Module | Outgoing Dependencies |\n|---|---|\n")
        for name, data in top_fan_out:
            report_parts.append(f"| `{name}` | {data['fan_out']} |\n")

        top_fan_in = sorted(info.items(), key=lambda item: item[1]["fan_in"], reverse=True)[:5]
        report_parts.append("\n### Highest Fan-In (Most Depended-On Modules)\n")
        report_parts.append("| Module | Incoming Dependencies |\n|---|---|\n")
        for name, data in top_fan_in:
            report_parts.append(f"| `{name}` | {data['fan_in']} |\n")
        
        # Layering violations
        violations = []
        for mod, deps in dep_analysis["graph"].items():
            if mod.startswith(f"{PACKAGE_NAME}.core"):
                for dep in deps:
                    if dep.startswith(f"{PACKAGE_NAME}.cli") or dep.startswith(f"{PACKAGE_NAME}.mcp"):
                        violations.append(f"`{mod}` -> `{dep}`")
        if violations:
            report_parts.append("\n### Architectural Layering Violations\n")
            report_parts.append("**WARNING**: Found dependencies from `core` layers to outer layers (`cli`, `mcp`). This violates the Dependency Rule and should be fixed.\n\n")
            report_parts.append("\n".join(f"- {v}" for v in violations))

    else:
        report_parts.append("Dependency analysis could not be performed.\n")

    # --- Circular Dependencies ---
    report_parts.append("\n## 3. Circular Dependency Check\n")
    if circular_deps:
        report_parts.append(
            f"**CRITICAL: Found {len(circular_deps)} circular dependency groups.** "
            "These create tight coupling and can lead to import errors and maintenance issues.\n"
        )
        for i, cycle in enumerate(circular_deps, 1):
            report_parts.append(f"\n### Cycle {i}\n")
            report_parts.append("```\n" + " ->\n".join(cycle) + "\n```\n")
        report_parts.append(
            "\n**Recommendation**: Break these cycles by using dependency inversion (e.g., introducing a `Protocol`), "
            "moving shared functionality to a new, lower-level module, or refactoring responsibilities.\n"
        )
    else:
        report_parts.append("**SUCCESS: No circular dependencies found.** This is a sign of a healthy, layered architecture.\n")

    # --- Interface & Contract Review ---
    report_parts.append("\n## 4. Interface and Contract Review (SOLID Principles)\n")
    protocols = interface_analysis["protocols"]
    report_parts.append(f"Found **{len(protocols)}** `Protocol` definitions, which supports the **Dependency Inversion Principle**.\n")
    
    fat_interfaces = [p for p, d in protocols.items() if len(d["methods"]) > PROTOCOL_METHOD_THRESHOLD]
    if fat_interfaces:
        report_parts.append(
            f"\n**Potential Issue (Interface Segregation Principle)**: The following {len(fat_interfaces)} protocols have more than {PROTOCOL_METHOD_THRESHOLD} methods and could be considered 'fat' interfaces. Consider splitting them into smaller, more focused protocols.\n"
        )
        report_parts.append("| Protocol | Method Count | Path |\n|---|---|---|\n")
        for name in fat_interfaces:
            data = protocols[name]
            report_parts.append(f"| `{name}` | {len(data['methods'])} | `{data['path']}` |\n")
    else:
        report_parts.append("\nNo 'fat' interfaces detected. Protocols appear well-scoped, adhering to the **Interface Segregation Principle**.\n")

    # --- Maintainability Metrics ---
    report_parts.append("\n## 5. Maintainability Metrics (Radon)\n")
    if maintainability_analysis:
        cc_data = maintainability_analysis["cc"]
        mi_data = maintainability_analysis["mi"]

        complex_items = []
        for path, blocks in cc_data.items():
            if isinstance(blocks, list):
                for block in blocks:
                    if block.get("rank") and block["complexity"] >= CYCLOMATIC_COMPLEXITY_THRESHOLD:
                        complex_items.append({
                            "path": path.replace(str(ROOT_DIR) + '/', ''),
                            "name": block["name"],
                            "type": block["type"],
                            "complexity": block["complexity"],
                            "rank": block["rank"],
                        })
        
        low_mi_files = []
        total_mi = 0
        file_count = 0
        for path, data in mi_data.items():
            if "mi" in data:
                total_mi += data["mi"]
                file_count += 1
                if data["mi"] < MAINTAINABILITY_INDEX_THRESHOLD:
                     low_mi_files.append({
                        "path": path.replace(str(ROOT_DIR) + '/', ''),
                        "mi": data["mi"],
                        "rank": data["rank"],
                    })
        
        avg_mi = total_mi / file_count if file_count > 0 else 0
        report_parts.append(f"Overall average Maintainability Index (MI) is **{avg_mi:.2f}** (Grade: {mi_data.get('average', {}).get('rank', 'N/A')}).\n")

        if complex_items:
            report_parts.append(f"\n**WARNING: Found {len(complex_items)} functions/methods with high Cyclomatic Complexity (>{CYCLOMATIC_COMPLEXITY_THRESHOLD}).** These are difficult to test and maintain.\n")
            report_parts.append("| Path | Name | Type | Complexity | Rank |\n|---|---|---|---|---|\n")
            for f in sorted(complex_items, key=lambda x: x['complexity'], reverse=True)[:10]:
                report_parts.append(f"| `{f['path']}` | `{f['name']}` | {f['type']} | **{f['complexity']}** | {f['rank']} |\n")
        else:
            report_parts.append("\n**SUCCESS: No functions with high Cyclomatic Complexity found.**\n")

        if low_mi_files:
            report_parts.append(f"\n**WARNING: Found {len(low_mi_files)} modules with low Maintainability Index (<{MAINTAINABILITY_INDEX_THRESHOLD}).** These modules may be hard to understand and modify.\n")
            report_parts.append("| Path | Maintainability Index | Rank |\n|---|---|---|\n")
            for f in sorted(low_mi_files, key=lambda x: x['mi']):
                report_parts.append(f"| `{f['path']}` | **{f['mi']:.2f}** | {f['rank']} |\n")
        else:
            report_parts.append("\n**SUCCESS: All modules have a good Maintainability Index.**\n")
    else:
        report_parts.append("Maintainability analysis could not be performed.\n")

    # --- Recommendations ---
    report_parts.append("\n## 6. Summary of Recommendations\n")
    recs = []
    if circular_deps:
        recs.append("1. **High Priority**: Refactor modules to break all identified circular dependencies. This is critical for a healthy architecture.")
    if maintainability_analysis and complex_items:
        recs.append("2. **Medium Priority**: Refactor functions/methods with high cyclomatic complexity. Focus on the most complex items, like `cmd_analyze` and `apply_suggestion`, by extracting logic into smaller, single-responsibility helper functions or classes.")
    if maintainability_analysis and low_mi_files:
        recs.append("3. **Medium Priority**: Review and refactor modules with a low maintainability index. Large modules like `analyzer_service.py` and `facade.py` are candidates for being split into smaller, more focused modules.")
    if dep_analysis and violations:
        recs.append("4. **High Priority**: Fix architectural layering violations. The `core` should not depend on `cli` or `mcp`. Use dependency inversion to pass information outwards.")
    if fat_interfaces:
        recs.append("5. **Low Priority**: Consider splitting large protocols into smaller, more specific ones to improve interface segregation.")
    
    if recs:
        report_parts.extend(recs)
    else:
        report_parts.append("No critical issues found. The architecture appears to be in good health. Continue to monitor these metrics as the project evolves.")

    print("   ...report generation complete.")
    return "\n".join(report_parts)


def cleanup():
    """Remove temporary files created during analysis."""
    print("6. Cleaning up temporary files...")
    for f in TEMP_FILES:
        if f.exists():
            try:
                f.unlink()
            except OSError as e:
                print(f"Warning: Could not remove temp file {f}: {e}")
    print("   ...cleanup complete.")


def main():
    """Main script execution."""
    print("Starting Pytest-Analyzer Architecture Review...")
    
    # Run analyses
    dep_analysis = analyze_dependencies()
    
    circular_deps = []
    if dep_analysis:
        circular_deps = find_circular_dependencies(dep_analysis["graph"])
    
    interface_analysis = analyze_interfaces_and_contracts()
    maintainability_analysis = analyze_maintainability()

    # Generate and save report
    report_content = generate_report(
        dep_analysis, circular_deps, interface_analysis, maintainability_analysis
    )
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    print(f"\nArchitecture review complete. Report saved to: {REPORT_PATH}")

    # Clean up
    cleanup()
    
    # Exit with error code if critical issues found
    if circular_deps:
        print("\nCritical issue found: Circular dependencies detected.")
        sys.exit(1)


if __name__ == "__main__":
    main()
