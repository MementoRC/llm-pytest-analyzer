"""
Debug script to understand and fix remaining tests
"""

import subprocess


def run_single_test(test_path):
    """Run a single test and capture output"""
    cmd = ["pixi", "run", "python", "-m", "pytest", test_path, "-xvs"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


# Tests that are failing when run together
failing_tests = [
    "tests/core/test_llm_service.py::TestLLMService::test_auto_detect_anthropic_client",
    "tests/core/test_llm_service.py::TestLLMService::test_auto_detect_openai_client",
    "tests/core/test_llm_service.py::TestLLMService::test_auto_detect_prefers_anthropic",
    "tests/core/test_llm_service.py::TestLLMService::test_auto_detect_anthropic_init_fails",
    "tests/core/test_llm_service.py::TestLLMService::test_auto_detect_openai_init_fails",
    "tests/integration/test_service_integration.py::test_service_integration_with_llm",
]

# Run each test individually
print("Running tests individually:")
for test in failing_tests:
    returncode, stdout, stderr = run_single_test(test)
    status = "PASSED" if returncode == 0 else "FAILED"
    print(f"{test}: {status}")

# Run them all together
print("\nRunning all failing tests together:")
cmd = ["pixi", "run", "python", "-m", "pytest"] + failing_tests + ["-xvs"]
result = subprocess.run(cmd, capture_output=True, text=True)
print(f"All together: {'PASSED' if result.returncode == 0 else 'FAILED'}")

# Run them in pairs to find interaction
print("\nTesting for interactions:")
for i in range(len(failing_tests)):
    for j in range(i + 1, len(failing_tests)):
        cmd = [
            "pixi",
            "run",
            "python",
            "-m",
            "pytest",
            failing_tests[i],
            failing_tests[j],
            "-xvs",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        status = "PASSED" if result.returncode == 0 else "FAILED"
        print(f"{failing_tests[i]} + {failing_tests[j]}: {status}")
