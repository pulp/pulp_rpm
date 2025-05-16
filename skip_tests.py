#!/usr/bin/env python3
"""
skip_tests.py - Check if only documentation files were changed in a git branch

This script compares the current branch with a reference branch and returns:
- Print 0 if only documentation files were modified (tests can be skipped)
- Print 1 if code or other non-documentation files were modified (tests should run)

Usage:
    python skip_tests.py [reference_branch]

Arguments:
    reference_branch: The branch to compare against (default: main)

Requirements:
    pip install gitpython
"""

import sys
import os
import re
import git
import textwrap

SKIP = 0
NO_SKIP = 1


def get_changed_files(reference_branch):
    """Get list of files changed between current branch and reference branch."""
    try:
        # Initialize repository object
        repo = git.Repo(os.getcwd())

        # Get the diff between current HEAD and reference branch
        diff_index = repo.git.diff("--name-only", reference_branch).strip()

        # Return list of changed files
        return diff_index.split("\n") if diff_index else []

    except git.GitCommandError as e:
        print(f"Git error: {e}", file=sys.stderr)
        sys.exit(2)
    except git.InvalidGitRepositoryError:
        print("Current directory is not a git repository", file=sys.stderr)
        sys.exit(2)


def is_doc_file(file_path):
    """Check if a file is a documentation file."""

    # Documentation file patterns
    doc_patterns = [
        r"^docs/",  # Files in docs directory
        r"^.+/docs/",  # Files in docs subdirectories
        r"^README\..*$",  # README files with any extension
        r"^.+/README\..*$",  # README files in subdirectories
        r"\.md$",  # Markdown files
        r"mkdocs\.yml$",  # MkDocs configuration
        r"\.txt$",  # Plain text files that might be documentation
        r"LICENSE.*",  # License files
        r"CHANGELOG.*",  # Changelog files
        r"CONTRIBUTING.*",  # Contributing guidelines
        r"HISTORY.*",  # Project history/changelog
        r"AUTHORS.*",  # Author information
        r"MAINTAINERS.*",  # Maintainer information
        r".github/workflows/ci.yml",
        r"skip_tests.py",
    ]

    # Check if the file matches any documentation pattern
    for pattern in doc_patterns:
        if re.search(pattern, file_path):
            return True

    return False


def main():
    if len(sys.argv) < 2:
        raise ValueError("Must provide a reference branch. E.g: main")

    reference_branch = sys.argv[1]
    changed_files = get_changed_files(reference_branch)
    if not changed_files or changed_files == [""]:
        return SKIP

    non_doc_files = [f for f in changed_files if not is_doc_file(f)]
    doc_files = set(changed_files) - set(non_doc_files)
    display_doc = "    \n".join(doc_files)

    print(f"doc_files({len(doc_files)})")
    if doc_files:
        display_doc = "\n".join(doc_files)
        print(textwrap.indent(display_doc, "    "))

    print(f"non_doc_files({len(non_doc_files)})")
    if non_doc_files:
        display_non_doc = "    \n".join(non_doc_files)
        print(textwrap.indent(display_non_doc, "    "))

    if non_doc_files:
        return NO_SKIP
    else:
        return SKIP


if __name__ == "__main__":
    sys.exit(main())
