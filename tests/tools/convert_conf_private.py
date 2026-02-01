#!/usr/bin/env python3
"""
Convert legacy conf_private.py to new test_servers.yaml format.

Usage:
    python tests/tools/convert_conf_private.py [conf_private.py] [output.yaml]

If no arguments given, looks for tests/conf_private.py and outputs to
tests/test_servers.yaml.

The old conf_private.py format is deprecated and will be removed in v3.0.
"""

import argparse
import sys
from pathlib import Path
from typing import Any


def load_conf_private(path: Path) -> dict[str, Any]:
    """Load configuration from conf_private.py file."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("conf_private", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def convert_to_yaml_config(conf_private: Any) -> dict[str, Any]:
    """Convert conf_private module to new YAML config format."""
    result: dict[str, Any] = {"test-servers": {}}
    servers = result["test-servers"]

    # Convert caldav_servers list
    if hasattr(conf_private, "caldav_servers"):
        for i, server in enumerate(conf_private.caldav_servers):
            name = server.get("name", f"server_{i}")
            # Normalize name for YAML key
            key = name.lower().replace(" ", "_").replace("-", "_")

            config: dict[str, Any] = {
                "type": "external",
                "enabled": server.get("enable", True),
            }

            # Map known keys
            key_mapping = {
                "url": "url",
                "username": "username",
                "password": "password",
                "ssl_verify_cert": "ssl_verify",
                "proxy": "proxy",
            }

            for old_key, new_key in key_mapping.items():
                if old_key in server:
                    config[new_key] = server[old_key]

            # Handle features list
            if "features" in server:
                config["features"] = server["features"]

            servers[key] = config

    # Handle boolean enable/disable switches
    server_names = [
        "radicale",
        "xandikos",
        "baikal",
        "nextcloud",
        "cyrus",
        "sogo",
        "bedework",
        "davical",
    ]

    for server_name in server_names:
        test_attr = f"test_{server_name}"
        if hasattr(conf_private, test_attr):
            if server_name not in servers:
                # Determine type based on server name
                if server_name in ("radicale", "xandikos"):
                    server_type = "embedded"
                else:
                    server_type = "docker"
                servers[server_name] = {"type": server_type}
            servers[server_name]["enabled"] = getattr(conf_private, test_attr)

    # Handle host/port overrides
    for server_name in server_names:
        host_attr = f"{server_name}_host"
        port_attr = f"{server_name}_port"

        if hasattr(conf_private, host_attr):
            if server_name not in servers:
                servers[server_name] = {}
            servers[server_name]["host"] = getattr(conf_private, host_attr)

        if hasattr(conf_private, port_attr):
            if server_name not in servers:
                servers[server_name] = {}
            servers[server_name]["port"] = getattr(conf_private, port_attr)

    # Handle username/password for known servers
    for server_name in server_names:
        user_attr = f"{server_name}_username"
        pass_attr = f"{server_name}_password"

        if hasattr(conf_private, user_attr):
            if server_name not in servers:
                servers[server_name] = {}
            servers[server_name]["username"] = getattr(conf_private, user_attr)

        if hasattr(conf_private, pass_attr):
            if server_name not in servers:
                servers[server_name] = {}
            servers[server_name]["password"] = getattr(conf_private, pass_attr)

    # Handle rfc6638_users
    if hasattr(conf_private, "rfc6638_users"):
        result["rfc6638_users"] = conf_private.rfc6638_users

    return result


def to_yaml(config: dict[str, Any], indent: int = 0) -> str:
    """Convert config dict to YAML string (simple implementation)."""
    lines = []
    prefix = "  " * indent

    for key, value in config.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(to_yaml(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    # First key on same line as dash
                    first = True
                    for k, v in item.items():
                        if first:
                            lines.append(f"{prefix}  - {k}: {format_value(v)}")
                            first = False
                        else:
                            lines.append(f"{prefix}    {k}: {format_value(v)}")
                else:
                    lines.append(f"{prefix}  - {format_value(item)}")
        else:
            lines.append(f"{prefix}{key}: {format_value(value)}")

    return "\n".join(lines)


def format_value(value: Any) -> str:
    """Format a value for YAML output."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, str):
        # Quote strings that might be ambiguous
        if (
            value in ("true", "false", "null", "yes", "no", "on", "off")
            or value.startswith("${")
            or ":" in value
            or "#" in value
        ):
            return f'"{value}"'
        return value
    else:
        return str(value)


def main():
    parser = argparse.ArgumentParser(description="Convert conf_private.py to test_servers.yaml")
    parser.add_argument(
        "input",
        nargs="?",
        default="tests/conf_private.py",
        help="Path to conf_private.py (default: tests/conf_private.py)",
    )
    parser.add_argument(
        "output",
        nargs="?",
        default="tests/test_servers.yaml",
        help="Output YAML file (default: tests/test_servers.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print output instead of writing to file",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        print(
            "\nIf you don't have a conf_private.py, copy the example instead:",
            file=sys.stderr,
        )
        print("  cp tests/test_servers.yaml.example tests/test_servers.yaml", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {input_path}...")
    conf_private = load_conf_private(input_path)

    print("Converting to new format...")
    config = convert_to_yaml_config(conf_private)

    # Generate YAML with header
    yaml_content = f"""# Test server configuration for caldav tests
# Converted from {input_path.name}
#
# See tests/README.md for documentation.

{to_yaml(config)}
"""

    if args.dry_run:
        print("\n--- Generated YAML ---")
        print(yaml_content)
    else:
        output_path.write_text(yaml_content)
        print(f"Written to {output_path}")
        print(f"\nYou can now delete {input_path} (it's deprecated and will be ignored)")


if __name__ == "__main__":
    main()
