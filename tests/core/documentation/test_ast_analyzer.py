from src.pytest_analyzer.core.documentation.docstring_parser import DocstringParser


def test_parse_google_style_docstring():
    def func():
        """
        Summary line.

        Args:
            x (int): The x value.
            y (str): The y value.

        Returns:
            bool: True if successful.

        Raises:
            ValueError: If x is invalid.
        """
        pass

    parser = DocstringParser()
    result = parser.parse(func)
    assert result["summary"].startswith("Summary line")
    assert result["params"][0]["name"] == "x"
    assert result["params"][0]["type"] == "int"
    assert result["returns"].startswith("bool")
    assert "ValueError" in "".join(result["raises"])


def test_parse_numpy_style_docstring():
    def func():
        """
        Summary line.

        Parameters
        ----------
        x : int
            The x value.
        y : str
            The y value.

        Returns
        -------
        bool
            True if successful.

        Raises
        ------
        ValueError
            If x is invalid.
        """
        pass

    parser = DocstringParser()
    result = parser.parse(func)
    assert result["summary"].startswith("Summary line")
    assert len(result["params"]) > 0, f"Expected params but got: {result}"
    assert result["params"][0]["name"] == "x"
    assert result["params"][0]["type"] == "int"
    assert result["returns"] is not None  # Returns should capture something
    assert any("ValueError" in r for r in result["raises"])


def test_parse_rst_style_docstring():
    def func():
        """
        Summary line.

        :param x: The x value.
        :type x: int
        :param y: The y value.
        :type y: str
        :returns: True if successful.
        :raises ValueError: If x is invalid.
        """
        pass

    parser = DocstringParser()
    result = parser.parse(func)
    assert result["summary"].startswith("Summary line")
    assert result["params"][0]["name"] == "x"
    assert result["params"][0]["type"] == "int"
    assert "True if successful" in result["returns"]
    assert any("invalid" in r for r in result["raises"])
