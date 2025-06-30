"""
CI Environment Detection Module

Detects CI environment and available tools for intelligent test execution.
Also provides CI-specific configuration recommendations.
"""

import logging
import os
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("pytest_analyzer.ci_detection")
logger.addHandler(logging.NullHandler())

# --- Configuration Recommendation Dataclasses ---


@dataclass(frozen=True)
class ConfigurationRecommendation:
    """Represents a CI configuration recommendation"""

    template_name: str
    platform: str
    language: str
    score: float
    config_content: str
    explanation: str


@dataclass(frozen=True)
class ConfigurationTemplate:
    """Represents a CI configuration template"""

    name: str
    platform: str
    language: str
    template_content: str


@dataclass(frozen=True)
class ProjectStructure:
    """Represents the structure of a project"""

    root_path: str
    has_pyproject: bool
    has_package_json: bool
    detected_languages: List[str]


# --- CI Detection Dataclasses ---


@dataclass(frozen=True)
class CIPlatform:
    name: str
    detected: bool
    raw_env: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolInfo:
    name: str
    found: bool
    path: Optional[str] = None
    version: Optional[str] = None


@dataclass(frozen=True)
class DetectionResult:
    platform: CIPlatform
    available_tools: List[ToolInfo]
    missing_tools: List[str]
    install_commands: Dict[str, str]


# --- Backward compatibility dataclass ---


@dataclass
class CIEnvironment:
    name: str
    detected: bool
    available_tools: List[str]
    missing_tools: List[str]
    tool_install_commands: Dict[str, str]


# --- Enhanced CIEnvironmentDetector ---


class CIEnvironmentDetector:
    """Detect CI environment and available tools (enhanced)"""

    _cache_lock = threading.Lock()
    _cache: Optional[DetectionResult] = None

    # --- Platform detection ---

    def detect_ci_platform(self) -> CIPlatform:
        """Detect which CI platform we're running on and return CIPlatform"""
        ci_indicators = {
            "github": "GITHUB_ACTIONS",
            "gitlab": "GITLAB_CI",
            "jenkins": "JENKINS_URL",
            "circleci": "CIRCLECI",
            "travis": "TRAVIS",
            "azure": "AZURE_PIPELINES",
        }
        env = {k: v for k, v in os.environ.items()}
        for provider, env_var in ci_indicators.items():
            if os.getenv(env_var):
                logger.info(f"Detected CI platform: {provider}")
                return CIPlatform(name=provider, detected=True, raw_env=env)
        logger.info("No CI platform detected, assuming local")
        return CIPlatform(name="local", detected=False, raw_env=env)

    # --- Tool scanning ---

    def scan_available_tools(self) -> List[ToolInfo]:
        """Scan for available security and development tools, with version info"""
        tools_to_check = [
            "bandit",
            "safety",
            "mypy",
            "ruff",
            "black",
            "pytest",
            "coverage",
            "pre-commit",
        ]
        found_tools: List[ToolInfo] = []
        for tool in tools_to_check:
            path = self._find_tool(tool)
            found = path is not None
            version = self._get_tool_version(tool, path) if found else None
            found_tools.append(
                ToolInfo(name=tool, found=found, path=path, version=version)
            )
        return found_tools

    def _find_tool(self, tool: str) -> Optional[str]:
        """Find tool in PATH or pixi env, return path or None"""
        try:
            path = shutil.which(tool)
            if path:
                return path
            # Check pixi env
            pixi_env_path = Path(".pixi/env/bin") / tool
            if pixi_env_path.exists():
                return str(pixi_env_path.resolve())
        except Exception as e:
            logger.error(f"Error finding tool {tool}: {e}")
        return None

    def _get_tool_version(self, tool: str, path: Optional[str]) -> Optional[str]:
        """Try to get the version of a tool by running '<tool> --version'"""
        if not path:
            return None
        import subprocess

        try:
            # Some tools print version to stderr, some to stdout
            result = subprocess.run(
                [path, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2,
            )
            output = result.stdout.strip() or result.stderr.strip()
            # Try to extract version number
            import re

            match = re.search(r"(\d+\.\d+\.\d+)", output)
            if match:
                return match.group(1)
            return output.split()[-1] if output else None
        except Exception as e:
            logger.warning(f"Could not get version for {tool}: {e}")
            return None

    # --- Missing tools ---

    def get_missing_tools(
        self, required_tools: List[str], available_tools: List[ToolInfo]
    ) -> List[str]:
        """Return list of required tools not found in available_tools"""
        available_names = {t.name for t in available_tools if t.found}
        return [tool for tool in required_tools if tool not in available_names]

    # --- Install commands ---

    def generate_install_commands(
        self, platform: CIPlatform, missing_tools: List[str]
    ) -> Dict[str, str]:
        """Get tool installation commands for specific CI platforms"""
        commands = {
            "github": {
                "bandit": "pip install bandit",
                "safety": "pip install safety",
                "mypy": "pip install mypy",
                "ruff": "pip install ruff",
            },
            "local": {
                "bandit": "pixi add bandit",
                "safety": "pixi add safety",
                "mypy": "pixi add mypy",
                "ruff": "pixi add ruff",
            },
        }
        platform_cmds = commands.get(platform.name, commands["local"])
        return {
            tool: platform_cmds.get(tool, f"pip install {tool}")
            for tool in missing_tools
        }

    # --- Caching ---

    def get_detection_result(self) -> DetectionResult:
        """Get full detection result, using cache if available"""
        with self._cache_lock:
            if self._cache is not None:
                logger.debug("Using cached DetectionResult")
                return self._cache
            try:
                platform = self.detect_ci_platform()
                available_tools = self.scan_available_tools()
                required_tools = ["bandit", "safety", "mypy", "ruff"]
                missing_tools = self.get_missing_tools(required_tools, available_tools)
                install_commands = self.generate_install_commands(
                    platform, missing_tools
                )
                result = DetectionResult(
                    platform=platform,
                    available_tools=available_tools,
                    missing_tools=missing_tools,
                    install_commands=install_commands,
                )
                self._cache = result
                logger.info("DetectionResult cached")
                return result
            except Exception as e:
                logger.error(f"Error during detection: {e}")
                raise

    def clear_cache(self):
        """Clear the detection result cache"""
        with self._cache_lock:
            self._cache = None
            logger.info("DetectionResult cache cleared")

    # --- Backward compatibility ---

    def detect_environment(self) -> CIEnvironment:
        """
        Backward compatible: Detect current CI environment and tool availability.
        """
        result = self.get_detection_result()
        return CIEnvironment(
            name=result.platform.name,
            detected=result.platform.detected,
            available_tools=[t.name for t in result.available_tools if t.found],
            missing_tools=result.missing_tools,
            tool_install_commands=result.install_commands,
        )

    # --- Legacy methods for compatibility ---

    def _detect_ci_provider(self) -> str:
        """Legacy: Detect which CI provider we're running on (returns str)"""
        return self.detect_ci_platform().name

    def _scan_available_tools(self) -> List[str]:
        """Legacy: Scan for available tools (returns list of names)"""
        tools_to_check = [
            "bandit",
            "safety",
            "mypy",
            "ruff",
            "black",
            "pytest",
            "coverage",
            "pre-commit",
        ]
        available = []
        for tool in tools_to_check:
            if shutil.which(tool) or self._check_pixi_tool(tool):
                available.append(tool)
        return available

    def _identify_missing_tools(self, available: List[str]) -> List[str]:
        """Legacy: Identify missing tools (from list of names)"""
        required_tools = ["bandit", "safety", "mypy", "ruff"]
        return [tool for tool in required_tools if tool not in available]

    def _get_install_commands(self, ci_provider: str) -> Dict[str, str]:
        """Legacy: Get install commands for provider (from str)"""
        platform = CIPlatform(name=ci_provider, detected=(ci_provider != "local"))
        # For legacy compatibility, assume all standard required tools are missing
        # to ensure comprehensive install commands are returned for the platform.
        # This bypasses the actual scan for the purpose of generating commands.
        required_tools_for_commands = ["bandit", "safety", "mypy", "ruff"]
        return self.generate_install_commands(platform, required_tools_for_commands)

    def _check_pixi_tool(self, tool: str) -> bool:
        """Legacy: Check if tool is available in pixi environment"""
        pixi_env_path = Path(".pixi/env/bin") / tool
        return pixi_env_path.exists()


# --- ConfigurationRecommender System ---


class ConfigurationRecommender:
    """Generate CI-specific configuration recommendations based on project analysis"""

    _cache_lock = threading.Lock()
    _structure_cache: Dict[str, ProjectStructure] = {}

    def __init__(self):
        """Initialize the configuration recommender"""
        self._templates = self._initialize_templates()

    def _initialize_templates(self) -> List[ConfigurationTemplate]:
        """Initialize built-in configuration templates"""
        return [
            ConfigurationTemplate(
                name="pytest-github",
                platform="github",
                language="python",
                template_content="""name: Python CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest ruff mypy
    - name: Run tests
      run: pytest
    - name: Run linting
      run: ruff check .
    - name: Run type checking
      run: mypy .""",
            ),
            ConfigurationTemplate(
                name="node-github",
                platform="github",
                language="node",
                template_content="""name: Node.js CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: ['18', '20', '22']
    steps:
    - uses: actions/checkout@v4
    - name: Use Node.js
      uses: actions/setup-node@v4
      with:
        node-version: ${{ matrix.node-version }}
    - name: Install dependencies
      run: npm ci
    - name: Run tests
      run: npm test
    - name: Run linting
      run: npm run lint""",
            ),
            ConfigurationTemplate(
                name="pytest-gitlab",
                platform="gitlab",
                language="python",
                template_content="""stages:
  - test
  - lint

test:python:
  stage: test
  image: python:3.12
  before_script:
    - pip install pytest ruff mypy
  script:
    - pytest
  parallel:
    matrix:
      - PYTHON_VERSION: ["3.10", "3.11", "3.12"]

lint:python:
  stage: lint
  image: python:3.12
  before_script:
    - pip install ruff mypy
  script:
    - ruff check .
    - mypy .""",
            ),
        ]

    def analyze_project_structure(self, project_path: str) -> ProjectStructure:
        """Analyze project structure to determine languages and configuration files"""
        with self._cache_lock:
            if project_path in self._structure_cache:
                logger.debug(f"Using cached project structure for {project_path}")
                return self._structure_cache[project_path]

        try:
            path = Path(project_path)
            if not path.exists():
                raise FileNotFoundError(f"Project path does not exist: {project_path}")

            has_pyproject = (path / "pyproject.toml").exists()
            has_package_json = (path / "package.json").exists()

            detected_languages = []
            if has_pyproject:
                detected_languages.append("python")
            if has_package_json:
                detected_languages.append("node")

            structure = ProjectStructure(
                root_path=project_path,
                has_pyproject=has_pyproject,
                has_package_json=has_package_json,
                detected_languages=detected_languages,
            )

            with self._cache_lock:
                self._structure_cache[project_path] = structure

            logger.info(
                f"Analyzed project structure for {project_path}: {detected_languages}"
            )
            return structure

        except Exception as e:
            logger.error(f"Error analyzing project structure: {e}")
            raise

    def _get_templates_for_platform(
        self, platform: str, language: str
    ) -> List[ConfigurationTemplate]:
        """Get templates matching the specified platform and language"""
        return [
            t
            for t in self._templates
            if t.platform == platform and t.language == language
        ]

    def get_recommendations_for_platform(
        self, platform: str, project_structure: ProjectStructure
    ) -> List[ConfigurationRecommendation]:
        """Get configuration recommendations for a specific platform"""
        recommendations = []

        for language in project_structure.detected_languages:
            templates = self._get_templates_for_platform(platform, language)

            for template in templates:
                score = self.score_recommendation(platform=platform, language=language)
                config_content = self.generate_configuration(template, {})
                explanation = self._generate_explanation(template, project_structure)

                recommendation = ConfigurationRecommendation(
                    template_name=template.name,
                    platform=platform,
                    language=language,
                    score=score,
                    config_content=config_content,
                    explanation=explanation,
                )
                recommendations.append(recommendation)

        # Sort by score (highest first)
        recommendations.sort(key=lambda r: r.score, reverse=True)
        logger.info(f"Generated {len(recommendations)} recommendations for {platform}")
        return recommendations

    def generate_configuration(
        self, template: ConfigurationTemplate, variables: Dict[str, str]
    ) -> str:
        """Generate configuration content from template"""
        if template is None:
            raise ValueError("Template cannot be None")

        try:
            config = template.template_content
            # Simple variable substitution (can be enhanced)
            for key, value in variables.items():
                config = config.replace(f"${{{key}}}", value)
            return config
        except Exception as e:
            logger.error(f"Error generating configuration: {e}")
            raise

    def validate_configuration(self, config_content: str) -> bool:
        """Validate configuration content (basic validation)"""
        if not config_content or not config_content.strip():
            return False

        try:
            # Basic YAML-like validation
            lines = config_content.strip().split("\n")
            if len(lines) < 1:
                return False

            # Check for basic structure (more permissive)
            if not any(
                line.strip().startswith(
                    ("name:", "on:", "stages:", "jobs:", "steps:", "script:")
                )
                for line in lines
            ):
                return False

            return True
        except Exception as e:
            logger.warning(f"Configuration validation error: {e}")
            return False

    def score_recommendation(self, platform: str, language: str, **kwargs) -> float:
        """Score a recommendation based on platform, language, and other factors"""
        return self._score_logic(platform, language, **kwargs)

    def _score_logic(self, platform: str, language: str, **kwargs) -> float:
        """Internal scoring logic"""
        base_score = 0.5

        # Platform scoring
        if platform == "github":
            base_score += 0.3
        elif platform == "gitlab":
            base_score += 0.2

        # Language scoring
        if language == "python":
            base_score += 0.2
        elif language == "node":
            base_score += 0.1

        return min(base_score, 1.0)

    def _generate_explanation(
        self, template: ConfigurationTemplate, project_structure: ProjectStructure
    ) -> str:
        """Generate explanation for why this template is recommended"""
        explanations = []

        explanations.append(
            f"Recommended {template.platform} configuration for {template.language} projects."
        )

        if template.language == "python" and project_structure.has_pyproject:
            explanations.append(
                "Detected pyproject.toml indicating Python project structure."
            )

        if template.language == "node" and project_structure.has_package_json:
            explanations.append(
                "Detected package.json indicating Node.js project structure."
            )

        explanations.append(
            f"Template '{template.name}' includes best practices for {template.platform} CI."
        )

        return " ".join(explanations)

    def get_configuration_recommendations(
        self, project_path: str, ci_platform: CIPlatform
    ) -> List[ConfigurationRecommendation]:
        """Main workflow: analyze project and generate recommendations"""
        try:
            structure = self.analyze_project_structure(project_path)
            recommendations = self.get_recommendations_for_platform(
                ci_platform.name, structure
            )
            logger.info(f"Generated {len(recommendations)} total recommendations")
            return recommendations
        except Exception as e:
            logger.error(f"Error getting configuration recommendations: {e}")
            raise

    def clear_cache(self):
        """Clear the project structure cache"""
        with self._cache_lock:
            self._structure_cache.clear()
            logger.info("Project structure cache cleared")


# --- CLI for manual testing ---


def main():
    """Command line interface for CI detection"""
    logging.basicConfig(level=logging.INFO)
    detector = CIEnvironmentDetector()
    result = detector.get_detection_result()
    print(f"CI Environment: {result.platform.name}")
    print(f"CI Detected: {result.platform.detected}")
    print("Available Tools:")
    for tool in result.available_tools:
        status = "FOUND" if tool.found else "MISSING"
        version = f" (v{tool.version})" if tool.version else ""
        print(f"  {tool.name}: {status}{version}")
    if result.missing_tools:
        print(f"Missing Tools: {', '.join(result.missing_tools)}")
        print("Install commands:")
        for tool in result.missing_tools:
            if tool in result.install_commands:
                print(f"  {tool}: {result.install_commands[tool]}")


if __name__ == "__main__":
    main()
