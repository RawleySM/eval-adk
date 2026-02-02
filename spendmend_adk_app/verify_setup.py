#!/usr/bin/env python3
"""
Verification script to check if the Spendmend ADK App is properly set up.

Run this after installation to verify:
- All modules can be imported
- All dependencies are installed
- Configuration is loadable
- Directory structure is correct
"""

import sys
import os
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.10 or higher."""
    print("Checking Python version...", end=" ")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} (requires 3.10+)")
        return False


def check_imports():
    """Check if all core modules can be imported."""
    print("\nChecking module imports...")

    modules = [
        "spendmend_adk",
        "spendmend_adk.settings",
        "spendmend_adk.schemas.common",
        "spendmend_adk.schemas.dev_task",
        "spendmend_adk.tools.jira_tools",
        "spendmend_adk.tools.github_tools",
        "spendmend_adk.services.session_service",
        "spendmend_adk.agents.workflow.root_loop",
    ]

    all_ok = True
    for module in modules:
        try:
            __import__(module)
            print(f"  ✓ {module}")
        except ImportError as e:
            print(f"  ✗ {module}: {e}")
            all_ok = False

    return all_ok


def check_dependencies():
    """Check if required dependencies are installed."""
    print("\nChecking dependencies...")

    dependencies = [
        "pydantic",
        "pydantic_settings",
        "google.adk",  # This might fail if google-adk isn't published yet
    ]

    all_ok = True
    for dep in dependencies:
        try:
            __import__(dep.replace(".", "/"))
            print(f"  ✓ {dep}")
        except ImportError:
            # google.adk might not be available yet, that's okay
            if dep == "google.adk":
                print(f"  ⚠ {dep} (optional - will be needed for execution)")
            else:
                print(f"  ✗ {dep}")
                all_ok = False

    return all_ok


def check_directory_structure():
    """Check if directory structure is correct."""
    print("\nChecking directory structure...")

    base_dir = Path(__file__).parent
    required_dirs = [
        "src/spendmend_adk",
        "src/spendmend_adk/schemas",
        "src/spendmend_adk/tools",
        "src/spendmend_adk/services",
        "src/spendmend_adk/agents",
        "src/spendmend_adk/agents/workflow",
        "src/spendmend_adk/agents/focus/spendmend_dev",
        "src/spendmend_adk/agents/builders",
        "src/spendmend_adk/eval",
    ]

    all_ok = True
    for dir_path in required_dirs:
        full_path = base_dir / dir_path
        if full_path.exists():
            print(f"  ✓ {dir_path}")
        else:
            print(f"  ✗ {dir_path}")
            all_ok = False

    return all_ok


def check_config_files():
    """Check if configuration files exist."""
    print("\nChecking configuration files...")

    base_dir = Path(__file__).parent
    config_files = [
        "pyproject.toml",
        ".env.example",
        "README.md",
        "SETUP.md",
    ]

    all_ok = True
    for file_name in config_files:
        file_path = base_dir / file_name
        if file_path.exists():
            print(f"  ✓ {file_name}")
        else:
            print(f"  ✗ {file_name}")
            all_ok = False

    # Check if .env exists (optional but recommended)
    env_path = base_dir / ".env"
    if env_path.exists():
        print(f"  ✓ .env (configured)")
    else:
        print(f"  ⚠ .env (not found - copy from .env.example)")

    return all_ok


def check_schemas():
    """Check if all schema files are present and importable."""
    print("\nChecking schema definitions...")

    try:
        from spendmend_adk.schemas import common, dev_task, pr_baseline, review, update_plan, eval

        schemas = [
            ("common.JiraRef", hasattr(common, "JiraRef")),
            ("common.RepoRef", hasattr(common, "RepoRef")),
            ("dev_task.SpendmendDevInput", hasattr(dev_task, "SpendmendDevInput")),
            ("dev_task.SpendmendDevOutput", hasattr(dev_task, "SpendmendDevOutput")),
            ("pr_baseline.BaselineFetchOutput", hasattr(pr_baseline, "BaselineFetchOutput")),
            ("review.GapReportOutput", hasattr(review, "GapReportOutput")),
            ("update_plan.AgentUpdaterOutput", hasattr(update_plan, "AgentUpdaterOutput")),
            ("eval.EvalRunnerOutput", hasattr(eval, "EvalRunnerOutput")),
        ]

        all_ok = True
        for name, exists in schemas:
            if exists:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
                all_ok = False

        return all_ok
    except ImportError as e:
        print(f"  ✗ Failed to import schemas: {e}")
        return False


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("Spendmend ADK App - Setup Verification")
    print("=" * 70)

    checks = [
        ("Python Version", check_python_version),
        ("Module Imports", check_imports),
        ("Dependencies", check_dependencies),
        ("Directory Structure", check_directory_structure),
        ("Configuration Files", check_config_files),
        ("Schema Definitions", check_schemas),
    ]

    results = []
    for name, check_func in checks:
        try:
            results.append((name, check_func()))
        except Exception as e:
            print(f"\n✗ {name} check failed with error: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:10} {name}")

    all_passed = all(passed for _, passed in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ All checks passed! Setup is complete.")
        print("\nNext steps:")
        print("1. Copy .env.example to .env and add your credentials")
        print("2. Implement tool functions in src/spendmend_adk/tools/")
        print("3. Run: python -m spendmend_adk.main")
    else:
        print("✗ Some checks failed. Please review the output above.")
        print("\nCommon fixes:")
        print("1. Install the package: pip install -e .")
        print("2. Ensure you're in the project directory")
        print("3. Check Python version: python --version")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
