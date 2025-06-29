#!/usr/bin/env python3

"""
Smart Test CLI Command

Provides intelligent test selection and execution for pytest-analyzer.
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..analysis.token_efficient_analyzer import TokenEfficientAnalyzer
from ..core.test_categorization.categorizer import TestCategorizer
from ..utils.settings import Settings, load_settings

# Import the new optimizer
try:
    from ..core.test_categorization.execution_order import TestExecutionOrderOptimizer
except ImportError:
    TestExecutionOrderOptimizer = None
    logger = logging.getLogger("pytest_analyzer.smart_test")
    logger.warning(
        "TestExecutionOrderOptimizer could not be imported. Order optimization features will be unavailable."
    )

# Create logger
logger = logging.getLogger("pytest_analyzer.smart_test")

# Setup rich console
console = Console()


class SmartTestCommand:
    """Command for intelligent test selection and execution."""

    def __init__(
        self,
        test_categorizer: Optional[TestCategorizer] = None,
        token_analyzer: Optional[TokenEfficientAnalyzer] = None,
        settings: Optional[Settings] = None,
        optimizer: Optional[Any] = None,
    ):
        """Initialize the command with required components."""
        self.test_categorizer = test_categorizer or TestCategorizer()
        self.token_analyzer = token_analyzer or TokenEfficientAnalyzer()
        self._initial_settings = settings
        self.optimizer = optimizer or (
            TestExecutionOrderOptimizer() if TestExecutionOrderOptimizer else None
        )

    def parse_arguments(self) -> argparse.Namespace:
        """Parse command line arguments for the smart-test command."""
        parser = argparse.ArgumentParser(
            prog="pytest-analyzer smart-test",
            description="Intelligently select and run relevant tests based on code changes",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        # Action options (mutually exclusive group)
        action_group = parser.add_mutually_exclusive_group()
        action_group.add_argument(
            "--all",
            action="store_true",
            help="Run all tests regardless of changes",
        )
        action_group.add_argument(
            "--category",
            choices=[
                "unit",
                "integration",
                "functional",
                "e2e",
                "performance",
                "security",
            ],
            help="Run tests of specific category only",
        )

        # Pytest options
        pytest_group = parser.add_argument_group("Pytest Options")
        pytest_group.add_argument(
            "--pytest-args",
            type=str,
            help="Additional arguments to pass to pytest",
        )

        # Output format options
        output_group = parser.add_argument_group("Output Options")
        output_group.add_argument(
            "--json",
            action="store_true",
            help="Output results in JSON format",
        )
        output_group.add_argument(
            "--output-file",
            type=str,
            help="Save report to specified file",
        )
        output_group.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Enable verbose output",
        )

        # Execution order optimization options
        optimization_group = parser.add_argument_group("Execution Order Optimization")
        optimization_group.add_argument(
            "--optimize-order",
            action="store_true",
            help="Enable test execution order optimization",
        )
        optimization_group.add_argument(
            "--parallel",
            action="store_true",
            help="Enable parallel execution planning",
        )
        optimization_group.add_argument(
            "--fast-fail",
            action="store_true",
            help="Prioritize tests likely to fail (fast-fail)",
        )
        optimization_group.add_argument(
            "--historical-data",
            action="store_true",
            help="Use historical failure data for optimization",
        )

        return parser.parse_args()

    def execute(self, args: Optional[argparse.Namespace] = None) -> int:
        """Execute the smart test command."""
        if args is None:
            args = self.parse_arguments()

        try:
            # Load settings
            _ = self._initial_settings or self._load_settings(None)

            # Set up logging based on verbosity
            if args.verbose:
                logging.getLogger("pytest_analyzer").setLevel(logging.DEBUG)

            # Categorize tests
            categorized_tests = self.categorize_tests(args)

            # Run tests
            test_results = self.run_tests(categorized_tests, args)

            # Analyze results
            analysis_results = self.analyze_results(test_results)

            # Generate and display report
            report = self._generate_report(
                categorized_tests, test_results, analysis_results
            )

            # Output report
            if args.output_file:
                self._save_report(report, args.output_file, args.json)
                console.print(f"✅ Report saved to: {args.output_file}")
            else:
                self._display_report(report, args.json)

            return 0 if test_results.get("success", False) else 1

        except Exception as e:
            console.print(f"❌ Error during smart test execution: {e}", style="red")
            logger.exception("Error during smart test execution")
            return 1

    def categorize_tests(self, args: argparse.Namespace) -> Dict[str, List[str]]:
        """Categorize tests based on arguments and file analysis."""
        # Find test files
        test_files = self._find_test_files(args)

        # Categorize using TestCategorizer
        categorized = {}
        for test_file in test_files:
            try:
                category = self.test_categorizer.categorize_test(Path(test_file))
                category_name = category.name.lower()

                if category_name not in categorized:
                    categorized[category_name] = []
                categorized[category_name].append(test_file)
            except Exception as e:
                logger.warning(f"Failed to categorize {test_file}: {e}")
                # Default to functional if categorization fails
                if "functional" not in categorized:
                    categorized["functional"] = []
                categorized["functional"].append(test_file)

        return categorized

    def run_tests(
        self, categorized_tests: Dict[str, List[str]], args: argparse.Namespace
    ) -> Dict[str, Any]:
        """
        Run the selected tests using pytest, with optional execution order optimization.

        If --optimize-order is enabled, uses TestExecutionOrderOptimizer to plan execution,
        apply dependency ordering, parallelization, and fast-fail strategies.
        """
        # Determine which tests to run
        tests_to_run = []

        if args.all:
            # Run all tests
            for test_list in categorized_tests.values():
                tests_to_run.extend(test_list)
        elif args.category:
            # Run specific category
            tests_to_run = categorized_tests.get(args.category, [])
        else:
            # Smart selection based on git changes
            tests_to_run = self._select_tests_by_changes(categorized_tests)

        if not tests_to_run:
            console.print("📭 No relevant tests found to run")
            return {"success": True, "tests_run": 0, "output": "No tests selected"}

        # Execution order optimization
        execution_plan = None
        dependency_graph = None
        parallel_groups = None
        optimization_benefits = None

        if args.optimize_order:
            if not self.optimizer:
                logger.warning(
                    "TestExecutionOrderOptimizer is not available. Skipping optimization."
                )
            else:
                try:
                    # Prepare optimizer options
                    optimizer_options = {
                        "parallel": args.parallel,
                        "fast_fail": args.fast_fail,
                        "historical_data": args.historical_data,
                    }
                    # Generate execution plan
                    execution_plan = self.optimizer.generate_execution_plan(
                        tests_to_run,
                        categorized_tests=categorized_tests,
                        options=optimizer_options,
                    )
                    # Extract dependency graph and parallel groups if available
                    dependency_graph = getattr(self.optimizer, "dependency_graph", None)
                    parallel_groups = (
                        execution_plan.get("parallel_groups")
                        if isinstance(execution_plan, dict)
                        else None
                    )
                    optimization_benefits = (
                        execution_plan.get("optimization_benefits")
                        if isinstance(execution_plan, dict)
                        else None
                    )

                    # Use the ordered/optimized test list
                    if (
                        isinstance(execution_plan, dict)
                        and "ordered_tests" in execution_plan
                    ):
                        tests_to_run = execution_plan["ordered_tests"]
                    elif isinstance(execution_plan, list):
                        tests_to_run = execution_plan
                    else:
                        logger.warning(
                            "Execution plan format not recognized, running tests in default order."
                        )

                except Exception as e:
                    logger.warning(f"Failed to optimize execution order: {e}")
                    # Fallback to default order

        # Build pytest command(s)
        def build_pytest_cmd(test_subset):
            cmd = ["python", "-m", "pytest"] + test_subset
            if args.pytest_args:
                cmd.extend(args.pytest_args.split())
            if args.verbose:
                cmd.append("-v")
            return cmd

        # Parallel execution
        if args.optimize_order and args.parallel and parallel_groups:
            # Run each group in parallel subprocesses
            import concurrent.futures

            results = []
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future_to_group = {
                        executor.submit(
                            subprocess.run,
                            build_pytest_cmd(group),
                            capture_output=True,
                            text=True,
                            timeout=300,
                        ): group
                        for group in parallel_groups
                        if group
                    }
                    for future in concurrent.futures.as_completed(future_to_group):
                        group = future_to_group[future]
                        try:
                            result = future.result()
                            results.append(
                                {
                                    "group": group,
                                    "returncode": result.returncode,
                                    "stdout": result.stdout,
                                    "stderr": result.stderr,
                                }
                            )
                        except Exception as exc:
                            results.append(
                                {
                                    "group": group,
                                    "returncode": 1,
                                    "stdout": "",
                                    "stderr": f"Exception: {exc}",
                                }
                            )
                # Aggregate results
                overall_success = all(r["returncode"] == 0 for r in results)
                output = "\n\n".join(r["stdout"] for r in results)
                errors = "\n\n".join(r["stderr"] for r in results if r["stderr"])
                return {
                    "success": overall_success,
                    "tests_run": sum(len(r["group"]) for r in results),
                    "output": output,
                    "errors": errors,
                    "returncode": 0 if overall_success else 1,
                    "parallel_groups": [r["group"] for r in results],
                    "dependency_graph": dependency_graph,
                    "execution_plan": execution_plan,
                    "optimization_benefits": optimization_benefits,
                }
            except Exception as e:
                return {
                    "success": False,
                    "tests_run": 0,
                    "output": "",
                    "errors": f"Parallel execution failed: {e}",
                    "returncode": 1,
                }

        # Sequential execution (default or optimized order)
        cmd = build_pytest_cmd(tests_to_run)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            return {
                "success": result.returncode == 0,
                "tests_run": len(tests_to_run),
                "output": result.stdout,
                "errors": result.stderr,
                "returncode": result.returncode,
                "dependency_graph": dependency_graph,
                "execution_plan": execution_plan,
                "parallel_groups": parallel_groups,
                "optimization_benefits": optimization_benefits,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "tests_run": len(tests_to_run),
                "output": "",
                "errors": "Tests timed out after 5 minutes",
                "returncode": 124,
            }
        except Exception as e:
            return {
                "success": False,
                "tests_run": len(tests_to_run),
                "output": "",
                "errors": str(e),
                "returncode": 1,
            }

    def analyze_results(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze test results using TokenEfficientAnalyzer."""
        if not test_results.get("output"):
            return {"summary": "No test output to analyze"}

        try:
            # Use TokenEfficientAnalyzer for failure analysis
            analysis = self.token_analyzer.analyze_pytest_output(test_results["output"])
            return {
                "summary": "Analysis completed",
                "analysis": analysis,
                "efficiency_score": getattr(analysis, "efficiency_score", 0.0),
            }
        except Exception as e:
            logger.warning(f"Failed to analyze results: {e}")
            return {"summary": f"Analysis failed: {e}"}

    def _find_test_files(self, args: argparse.Namespace) -> List[str]:
        """Find test files to analyze."""
        test_files = []

        # Look for test files in common locations
        test_dirs = ["tests", "test"]
        for test_dir in test_dirs:
            test_path = Path(test_dir)
            if test_path.exists():
                test_files.extend([str(p) for p in test_path.rglob("test_*.py")])
                test_files.extend([str(p) for p in test_path.rglob("*_test.py")])

        return list(set(test_files))  # Remove duplicates

    def _select_tests_by_changes(
        self, categorized_tests: Dict[str, List[str]]
    ) -> List[str]:
        """Select tests based on git changes."""
        try:
            # Get changed files from git
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                # If git fails, run all tests
                tests = []
                for test_list in categorized_tests.values():
                    tests.extend(test_list)
                return tests

            changed_files = (
                result.stdout.strip().split("\n") if result.stdout.strip() else []
            )

            # Simple heuristic: if source files changed, run unit and integration tests
            # If test files changed, run those specific tests
            selected_tests = []

            for file in changed_files:
                if file.endswith(".py"):
                    if "test" in file:
                        # Test file changed, run it if it exists in our categorized tests
                        for test_list in categorized_tests.values():
                            if file in test_list:
                                selected_tests.append(file)
                    else:
                        # Source file changed, run related unit and integration tests
                        selected_tests.extend(categorized_tests.get("unit", []))
                        selected_tests.extend(categorized_tests.get("integration", []))

            return list(set(selected_tests))  # Remove duplicates

        except Exception as e:
            logger.warning(f"Failed to detect changes: {e}")
            # Fallback to unit tests
            return categorized_tests.get("unit", [])

    def _generate_report(
        self,
        categorized_tests: Dict[str, List[str]],
        test_results: Dict[str, Any],
        analysis_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate comprehensive report."""
        return {
            "categorization": categorized_tests,
            "execution": test_results,
            "analysis": analysis_results,
            "summary": {
                "total_categories": len(categorized_tests),
                "total_test_files": sum(
                    len(tests) for tests in categorized_tests.values()
                ),
                "tests_executed": test_results.get("tests_run", 0),
                "execution_success": test_results.get("success", False),
            },
        }

    def _save_report(self, report: Dict[str, Any], output_file: str, json_format: bool):
        """Save report to file."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if json_format:
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)
        else:
            with open(output_path, "w") as f:
                f.write(self._format_text_report(report))

    def _display_report(self, report: Dict[str, Any], json_format: bool):
        """Display report to console."""
        if json_format:
            print(json.dumps(report, indent=2))
        else:
            self._display_rich_report(report)

    def _display_rich_report(self, report: Dict[str, Any]):
        """Display rich-formatted report to console."""
        summary = report["summary"]

        # Header
        console.print(
            Panel(
                f"Smart Test Report - {summary['tests_executed']} tests executed",
                title="🧠 Smart Test Execution",
                border_style="green" if summary["execution_success"] else "red",
            )
        )

        # Test categorization
        categorization = report["categorization"]
        if categorization:
            cat_table = Table(title="Test Categorization")
            cat_table.add_column("Category", style="cyan")
            cat_table.add_column("Test Count", style="white")

            for category, tests in categorization.items():
                cat_table.add_row(category.title(), str(len(tests)))

            console.print(cat_table)

        # Execution results
        execution = report["execution"]
        exec_table = Table(title="Execution Summary")
        exec_table.add_column("Metric", style="cyan")
        exec_table.add_column("Value", style="white")

        exec_table.add_row("Tests Run", str(execution.get("tests_run", 0)))
        exec_table.add_row("Success", "✅ Yes" if execution.get("success") else "❌ No")
        exec_table.add_row("Return Code", str(execution.get("returncode", "N/A")))

        console.print(exec_table)

        # Execution order optimization reporting
        if execution.get("dependency_graph"):
            console.print("\n[magenta]🔗 Dependency Graph:[/magenta]")
            dep_graph = execution["dependency_graph"]
            if isinstance(dep_graph, dict):
                for node, deps in dep_graph.items():
                    console.print(f"  [bold]{node}[/bold] -> {deps}")
            else:
                console.print(str(dep_graph))

        if execution.get("execution_plan"):
            console.print("\n[yellow]🗺️ Execution Plan:[/yellow]")
            plan = execution["execution_plan"]
            if isinstance(plan, dict):
                for k, v in plan.items():
                    if k == "ordered_tests":
                        console.print(f"  [bold]Ordered Tests:[/bold] {v}")
                    elif k == "parallel_groups":
                        continue  # Shown below
                    elif k == "optimization_benefits":
                        continue  # Shown below
                    else:
                        console.print(f"  [bold]{k}:[/bold] {v}")
            else:
                console.print(str(plan))

        if execution.get("parallel_groups"):
            console.print("\n[cyan]⚡ Parallel Execution Groups:[/cyan]")
            for idx, group in enumerate(execution["parallel_groups"], 1):
                console.print(f"  Group {idx}: {group}")

        if execution.get("optimization_benefits"):
            console.print("\n[green]📈 Optimization Benefits:[/green]")
            console.print(str(execution["optimization_benefits"]))

        # Analysis results
        analysis = report["analysis"]
        if "analysis" in analysis:
            console.print(f"\n[blue]📊 Analysis:[/blue] {analysis['summary']}")

    def _format_text_report(self, report: Dict[str, Any]) -> str:
        """Format report as plain text."""
        lines = ["Smart Test Report", "=" * 50, ""]

        summary = report["summary"]
        lines.extend(
            [
                f"Total Categories: {summary['total_categories']}",
                f"Total Test Files: {summary['total_test_files']}",
                f"Tests Executed: {summary['tests_executed']}",
                f"Execution Success: {summary['execution_success']}",
                "",
            ]
        )

        # Categorization
        lines.append("Test Categorization:")
        for category, tests in report["categorization"].items():
            lines.append(f"  {category.title()}: {len(tests)} tests")
        lines.append("")

        # Execution order optimization reporting (plain text)
        execution = report.get("execution", {})
        if execution.get("dependency_graph"):
            lines.append("Dependency Graph:")
            dep_graph = execution["dependency_graph"]
            if isinstance(dep_graph, dict):
                for node, deps in dep_graph.items():
                    lines.append(f"  {node} -> {deps}")
            else:
                lines.append(str(dep_graph))
            lines.append("")
        if execution.get("execution_plan"):
            lines.append("Execution Plan:")
            plan = execution["execution_plan"]
            if isinstance(plan, dict):
                for k, v in plan.items():
                    if k == "ordered_tests":
                        lines.append(f"  Ordered Tests: {v}")
                    elif k == "parallel_groups":
                        continue
                    elif k == "optimization_benefits":
                        continue
                    else:
                        lines.append(f"  {k}: {v}")
            else:
                lines.append(str(plan))
            lines.append("")
        if execution.get("parallel_groups"):
            lines.append("Parallel Execution Groups:")
            for idx, group in enumerate(execution["parallel_groups"], 1):
                lines.append(f"  Group {idx}: {group}")
            lines.append("")
        if execution.get("optimization_benefits"):
            lines.append("Optimization Benefits:")
            lines.append(str(execution["optimization_benefits"]))
            lines.append("")

        # Analysis
        analysis = report["analysis"]
        lines.append(f"Analysis: {analysis['summary']}")

        return "\n".join(lines)

    def _load_settings(self, config_file: Optional[str]) -> Settings:
        """Load settings from configuration file."""
        try:
            return load_settings(config_file)
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")
            return Settings()


def main():
    """Main entry point for the smart-test command."""
    command = SmartTestCommand()
    return command.execute()


if __name__ == "__main__":
    sys.exit(main())
