"""
Tests for ConfigurationRecommender system in ci_detection.py
"""

import threading

import pytest

from pytest_analyzer.core.infrastructure.ci_detection import (
    CIPlatform,
    ConfigurationRecommendation,
    ConfigurationRecommender,
    ConfigurationTemplate,
    ProjectStructure,
)

# --- Fixtures for reusable test data ---


@pytest.fixture
def python_project(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.poetry]\nname = 'example'\n")
    return tmp_path


@pytest.fixture
def node_project(tmp_path):
    package_json = tmp_path / "package.json"
    package_json.write_text('{"name": "example-node"}')
    return tmp_path


@pytest.fixture
def mixed_project(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.poetry]\nname = 'example'\n")
    package_json = tmp_path / "package.json"
    package_json.write_text('{"name": "example-node"}')
    return tmp_path


@pytest.fixture
def empty_project(tmp_path):
    return tmp_path


@pytest.fixture
def ci_platform_github():
    return CIPlatform(name="github", detected=True, raw_env={"GITHUB_ACTIONS": "true"})


@pytest.fixture
def ci_platform_gitlab():
    return CIPlatform(name="gitlab", detected=True, raw_env={"GITLAB_CI": "true"})


@pytest.fixture
def ci_platform_local():
    return CIPlatform(name="local", detected=False, raw_env={})


@pytest.fixture
def config_template_python():
    return ConfigurationTemplate(
        name="pytest-github",
        platform="github",
        language="python",
        template_content="name: Python CI\non: [push]\n...",
    )


@pytest.fixture
def valid_config():
    return "name: Python CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest"


@pytest.fixture
def invalid_config():
    return "INVALID CONFIG"


# --- Dataclass validation tests ---


def test_configuration_recommendation_dataclass():
    rec = ConfigurationRecommendation(
        template_name="pytest-github",
        platform="github",
        language="python",
        score=0.95,
        config_content="name: Python CI\non: [push]",
        explanation="Recommended for Python projects on GitHub.",
    )
    assert rec.template_name == "pytest-github"
    assert rec.platform == "github"
    assert rec.language == "python"
    assert rec.score == 0.95
    assert "Python CI" in rec.config_content
    assert "Recommended" in rec.explanation


def test_configuration_template_dataclass():
    tmpl = ConfigurationTemplate(
        name="pytest-github",
        platform="github",
        language="python",
        template_content="name: Python CI\non: [push]",
    )
    assert tmpl.name == "pytest-github"
    assert tmpl.platform == "github"
    assert tmpl.language == "python"
    assert "Python CI" in tmpl.template_content


def test_project_structure_dataclass():
    struct = ProjectStructure(
        root_path="/tmp/project",
        has_pyproject=True,
        has_package_json=False,
        detected_languages=["python"],
    )
    assert struct.root_path == "/tmp/project"
    assert struct.has_pyproject is True
    assert struct.has_package_json is False
    assert struct.detected_languages == ["python"]


# --- ConfigurationRecommender class method tests ---


@pytest.mark.parametrize(
    "fixture_name,expected_langs,expected_py,expected_node",
    [
        ("python_project", ["python"], True, False),
        ("node_project", ["node"], False, True),
        ("mixed_project", ["python", "node"], True, True),
        ("empty_project", [], False, False),
    ],
)
def test_analyze_project_structure(
    fixture_name, expected_langs, expected_py, expected_node, request
):
    project = request.getfixturevalue(fixture_name)
    recommender = ConfigurationRecommender()
    struct = recommender.analyze_project_structure(str(project))
    assert set(struct.detected_languages) == set(expected_langs)
    assert struct.has_pyproject is expected_py
    assert struct.has_package_json is expected_node


def test_generate_configuration(config_template_python):
    recommender = ConfigurationRecommender()
    config = recommender.generate_configuration(config_template_python, {})
    assert isinstance(config, str)
    assert "Python CI" in config


def test_validate_configuration_valid(valid_config):
    recommender = ConfigurationRecommender()
    assert recommender.validate_configuration(valid_config) is True


def test_validate_configuration_invalid(invalid_config):
    recommender = ConfigurationRecommender()
    assert recommender.validate_configuration(invalid_config) is False


@pytest.mark.parametrize(
    "platform,language,expected_min_score",
    [
        ("github", "python", 0.9),
        ("github", "node", 0.8),
        ("gitlab", "python", 0.7),
        ("local", "python", 0.5),
    ],
)
def test_score_recommendation(platform, language, expected_min_score):
    recommender = ConfigurationRecommender()
    score = recommender.score_recommendation(platform=platform, language=language)
    assert score >= expected_min_score


def test_get_configuration_recommendations_workflow(python_project, ci_platform_github):
    recommender = ConfigurationRecommender()
    recs = recommender.get_configuration_recommendations(
        str(python_project), ci_platform_github
    )
    assert isinstance(recs, list)
    assert len(recs) > 0
    assert all(isinstance(r, ConfigurationRecommendation) for r in recs)


def test_error_handling_invalid_path():
    recommender = ConfigurationRecommender()
    with pytest.raises(FileNotFoundError):
        recommender.analyze_project_structure("/non/existent/path")


def test_error_handling_invalid_template():
    recommender = ConfigurationRecommender()
    with pytest.raises(ValueError):
        recommender.generate_configuration(None, {})


def test_caching_mechanism(python_project):
    recommender = ConfigurationRecommender()

    # First analysis should cache the result
    struct1 = recommender.analyze_project_structure(str(python_project))
    struct2 = recommender.analyze_project_structure(str(python_project))

    # Should be the same object from cache
    assert struct1 is struct2


def test_clear_cache(python_project):
    recommender = ConfigurationRecommender()

    # Analyze and cache
    struct1 = recommender.analyze_project_structure(str(python_project))

    # Clear cache
    recommender.clear_cache()

    # Should get new instance after cache clear
    struct2 = recommender.analyze_project_structure(str(python_project))
    assert struct1 is not struct2


def test_thread_safety(python_project, ci_platform_github):
    recommender = ConfigurationRecommender()
    results = []
    errors = []

    def worker():
        try:
            recs = recommender.get_configuration_recommendations(
                str(python_project), ci_platform_github
            )
            results.append(recs)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 5
    assert all(isinstance(r, list) for r in results)


# --- Edge cases and integration tests ---


def test_mixed_project_recommendations(mixed_project, ci_platform_github):
    recommender = ConfigurationRecommender()
    recs = recommender.get_configuration_recommendations(
        str(mixed_project), ci_platform_github
    )

    # Should have recommendations for both languages
    languages = [r.language for r in recs]
    assert "python" in languages
    assert "node" in languages


def test_no_language_detected(empty_project, ci_platform_github):
    recommender = ConfigurationRecommender()
    recs = recommender.get_configuration_recommendations(
        str(empty_project), ci_platform_github
    )
    assert recs == []


@pytest.mark.parametrize(
    "config,expected",
    [
        (
            "name: Python CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest",
            True,
        ),
        ("INVALID CONFIG", False),
        ("", False),
        ("   ", False),
        ("name: Test", True),  # Minimal valid config
    ],
)
def test_validate_configuration_parameterized(config, expected):
    recommender = ConfigurationRecommender()
    assert recommender.validate_configuration(config) is expected


def test_get_templates_for_platform():
    recommender = ConfigurationRecommender()

    # Test internal template matching
    python_github_templates = recommender._get_templates_for_platform(
        "github", "python"
    )
    assert len(python_github_templates) > 0
    assert all(
        t.platform == "github" and t.language == "python"
        for t in python_github_templates
    )

    node_github_templates = recommender._get_templates_for_platform("github", "node")
    assert len(node_github_templates) > 0
    assert all(
        t.platform == "github" and t.language == "node" for t in node_github_templates
    )


def test_explanation_generation(python_project):
    recommender = ConfigurationRecommender()
    structure = recommender.analyze_project_structure(str(python_project))

    template = ConfigurationTemplate(
        name="test-template",
        platform="github",
        language="python",
        template_content="test content",
    )

    explanation = recommender._generate_explanation(template, structure)
    assert "github" in explanation.lower()
    assert "python" in explanation.lower()
    assert "pyproject.toml" in explanation.lower()


def test_variable_substitution_in_configuration():
    recommender = ConfigurationRecommender()
    template = ConfigurationTemplate(
        name="test-template",
        platform="github",
        language="python",
        template_content="name: ${project_name}\nversion: ${version}",
    )

    variables = {"project_name": "MyProject", "version": "1.0.0"}
    config = recommender.generate_configuration(template, variables)

    assert "MyProject" in config
    assert "1.0.0" in config
    assert "${project_name}" not in config
    assert "${version}" not in config
