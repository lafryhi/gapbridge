"""Minimal local verification of the Strands Agents SDK setup.

This script performs ONLY local, offline checks:
  1. The strands SDK imports successfully.
  2. Core SDK objects (Agent, tool) are available.
  3. The strands-agents-tools package imports.
  4. Whether AWS credentials/configuration exist (presence only - values are never read or printed).

It deliberately does NOT invoke any model (no Bedrock calls, no paid API calls,
no cloud resources). Model invocation is intentionally skipped because this AWS
account currently returns "ValidationException: Operation not allowed" while
Bedrock account verification is pending.
"""

import sys

PASS = "PASS"
FAIL = "FAIL"


def main() -> int:
    print("=== Strands Agents SDK - local verification ===\n")

    # 1) SDK import check
    try:
        import strands  # noqa: F401
        from importlib.metadata import version

        sdk_version = version("strands-agents")
        print(f"[{PASS}] strands SDK imported successfully (version {sdk_version})")
    except Exception as exc:  # noqa: BLE001
        print(f"[{FAIL}] Could not import strands SDK: {exc}")
        return 1

    # 2) Core object availability check (local only, no network)
    try:
        from strands import Agent, tool  # noqa: F401

        print(f"[{PASS}] core objects available: Agent, tool")
    except Exception as exc:  # noqa: BLE001
        print(f"[{FAIL}] Core Strands objects unavailable: {exc}")
        return 1

    # 3) Tools package import check (local only, no tool execution)
    try:
        from strands_tools import calculator  # noqa: F401

        tools_version = None
        try:
            from importlib.metadata import version as _v

            tools_version = _v("strands-agents-tools")
        except Exception:  # noqa: BLE001
            pass
        suffix = f" (version {tools_version})" if tools_version else ""
        print(f"[{PASS}] strands-agents-tools imported successfully{suffix}")
    except Exception as exc:  # noqa: BLE001
        print(f"[{FAIL}] strands-agents-tools import failed: {exc}")
        return 1

    # 4) AWS configuration presence check - presence only, never values
    import os
    from pathlib import Path

    has_env_credentials = bool(
        os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_PROFILE")
    )
    aws_dir = Path.home() / ".aws"
    has_aws_files = aws_dir.is_dir() and any(aws_dir.iterdir())
    if has_env_credentials or has_aws_files:
        print("[INFO] AWS credentials/configuration detected (details not shown)")
    else:
        print("[INFO] No AWS credentials/configuration detected on this machine")

    # Status summary - clearly distinguishing the two concerns
    print("\n=== Summary ===")
    print("(a) SDK installed successfully: YES")
    print(
        "(b) AWS model invocation: NOT ATTEMPTED by design. "
        "This account is still pending Bedrock account verification "
        '(known issue: "ValidationException: Operation not allowed"), '
        "so no Bedrock/paid API call was made."
    )
    print("\nLocal environment verification completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
