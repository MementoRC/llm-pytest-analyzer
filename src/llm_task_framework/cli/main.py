"""CLI entry point for the LLM Task Framework."""

import asyncio

import click

from llm_task_framework.core.facade import TaskFramework
from llm_task_framework.core.models.config import TaskConfig
from llm_task_framework.mcp.server import MCPServer


@click.group()
def cli():
    """LLM Task Framework CLI."""


@cli.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "http"]),
    default="stdio",
    help="MCP server transport",
)
def mcp_server(transport):
    """Start the MCP server."""
    server = MCPServer(transport=transport)
    server.discover_tools()
    asyncio.run(server.run())


@cli.command()
def list_tasks():
    """List all registered tasks."""
    registry = TaskFramework.registry()
    for task_type in registry.list():
        meta = registry.get_metadata(task_type)
        click.echo(f"{task_type}: {meta.get('description', '')}")


@cli.command()
@click.argument("task_type")
@click.option("--param", multiple=True, help="Task parameter in key=value format")
def run_task(task_type, param):
    """Run a registered task."""
    params = {}
    for p in param:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k] = v
    config = TaskConfig(name=task_type, parameters=params)
    task = TaskFramework.create(task_type, config)
    result = TaskFramework.run(task, params)
    click.echo(f"Result: {result}")


@cli.command()
@click.argument("config_path")
def show_config(config_path):
    """Show configuration from a file (YAML/JSON)."""
    import json
    import os

    import yaml

    if not os.path.exists(config_path):
        click.echo("Config file not found.")
        return
    with open(config_path, "r") as f:
        if config_path.endswith(".json"):
            data = json.load(f)
        else:
            data = yaml.safe_load(f)
    click.echo(data)


def main():
    cli()


if __name__ == "__main__":
    main()
