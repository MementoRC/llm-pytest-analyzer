#!/usr/bin/env python3
"""
Quick test to debug the extraction pattern issue.
"""

import re

# Current pattern from the extractor
current_pattern = re.compile(r"(FAILED|ERROR)\s+(.+?)::(.+?)(?:\s|$)")

# Sample output from the actual pytest run
sample_output = """ERROR tests/gui/test_reporting_features.py::TestReportingIntegration::test_main_controller_has_report_controller
ERROR tests/gui/test_reporting_features.py::TestGUIWorkflowIntegration::test_report_menu_actions_connected
ERROR tests/gui/test_reporting_features.py::TestGUIWorkflowIntegration::test_generate_report_action_trigger
ERROR tests/gui/test_reporting_features.py::TestGUIWorkflowIntegration::test_quick_html_report_action_trigger
ERROR tests/gui/test_reporting_features.py::TestGUIWorkflowIntegration::test_export_actions_trigger
ERROR tests/gui/test_reporting_features.py::TestGUIWorkflowIntegration::test_keyboard_shortcuts"""

print("Testing current pattern:")
matches = current_pattern.findall(sample_output)
print(f"Found {len(matches)} matches with current pattern")
for match in matches:
    print(f"  {match}")

# Proposed fixed pattern - make the space optional
fixed_pattern = re.compile(r"(FAILED|ERROR)\s*(.+?)::(.+?)(?:\s|$)")

print("\nTesting fixed pattern:")
matches = fixed_pattern.findall(sample_output)
print(f"Found {len(matches)} matches with fixed pattern")
for match in matches:
    print(f"  {match}")
