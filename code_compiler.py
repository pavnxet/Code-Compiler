#!/usr/bin/env python3
"""
Code Compiler – Collect & Reconstruct Project Source Files
===========================================================

A single tool to archive a project's source code into one text file,
and later rebuild the exact folder structure from that archive.

Usage:
    python code_compiler.py collect [options]
    python code_compiler.py reconstruct DUMP_FILE [options]

Examples:
    # Collect all code from current directory into code_dump.txt
    python code_compiler.py collect -o code_dump.txt

    # Rebuild the project into ./restored
    python code_compiler.py reconstruct code_dump.txt

    # Rebuild with confirmation and overwrite
    python code_compiler.py reconstruct code_dump.txt --force --confirm

Made with 💖 by pavnxet
https://github.com/pavnxet/Code-Compiler
"""

import os
import sys
import argparse
import tempfile
import stat
from pathlib import Path
from typing import Iterator, Tuple, Set, List, Optional

# ----------------------------------------------------------------------
# Shared Constants & Helpers
# ----------------------------------------------------------------------
HEADER_SEP = "=" * 80

# File extensions and base names to include when collecting
DEFAULT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".scss", ".sass",
    ".c", ".cpp", ".h", ".hpp", ".java", ".kt", ".kts", ".swift", ".go", ".rs",
    ".rb", ".php", ".pl", ".pm", ".sh", ".bash", ".zsh", ".fish",
    ".sql", ".r", ".m", ".mm", ".lua", ".vim",
    ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg", ".conf",
    ".md", ".rst", ".tex", ".txt", ".csv",
    "Dockerfile", "Makefile", "CMakeLists.txt", "requirements.txt", "Gemfile",
    "package.json", "Cargo.toml", "go.mod", "go.sum",
}

# Directories to skip during collection (exact names or wildcard suffixes)
EXCLUDE_DIRS = {
    ".git", ".svn", ".hg", "__pycache__",
    "node_modules", "venv", ".venv", "env", ".env", "virtualenv",
    "dist", "build", "target", "out",
    ".idea", ".vscode", ".DS_Store",
    ".mypy_cache", ".pytest_cache", ".tox", ".eggs",
    "*.egg-info",      # pattern: ends with .egg-info
}

# ----------------------------------------------------------------------
# Security & Utility Functions
# ----------------------------------------------------------------------
def same_file(path1: str, path2: str) -> bool:
    """Cross‑platform same‑file check (handles case‑insensitivity)."""
    try:
        # Python 3.3+
        return os.path.samefile(path1, path2)
    except AttributeError:
        # Fallback: normalize case and resolve absolute paths
        return os.path.normcase(os.path.abspath(path1)) == os.path.normcase(os.path.abspath(path2))

def safe_path(output_root: str, rel_path: str) -> str:
    """
    Resolve a relative path within output_root; raise if escapes.
    Normalizes path separators for the current OS.
    """
    # Convert any backslashes to forward slashes for cross‑platform consistency
    rel_path = rel_path.replace('\\', '/')
    root = Path(output_root).resolve()
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"Attempted directory traversal: {rel_path}")
    return str(target)

def atomic_write(filepath: str, content: bytes, mode: Optional[int] = None):
    """
    Write content atomically using a temporary file.
    If mode is None, preserve permissions of existing file or use 0o644.
    """
    dirname = os.path.dirname(filepath)
    # Determine desired permission mode
    if mode is None:
        if os.path.exists(filepath):
            mode = stat.S_IMODE(os.stat(filepath).st_mode)
        else:
            mode = 0o644

    with tempfile.NamedTemporaryFile(dir=dirname, delete=False) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_name = tmp.name

    os.chmod(temp_name, mode)
    os.replace(temp_name, filepath)

def is_text_file(filepath: str) -> bool:
    """Heuristic: read first 1KB; no null byte -> likely text."""
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            return b'\x00' not in chunk
    except Exception:
        return False

def read_file_content(filepath: str) -> str:
    """Read file with encoding fallbacks."""
    for enc in ('utf-8', 'utf-16', 'latin-1'):
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    # Ultimate fallback
    with open(filepath, 'rb') as f:
        return f.read().decode('utf-8', errors='replace')

def should_exclude_directory(dirname: str) -> bool:
    """Check if a directory name matches any exclusion pattern."""
    for pat in EXCLUDE_DIRS:
        if pat.startswith('*') and dirname.endswith(pat[1:]):
            return True
        if dirname == pat:
            return True
    return False

# ----------------------------------------------------------------------
# COLLECT MODE
# ----------------------------------------------------------------------
def should_include_file(filepath: str, extensions: Set[str]) -> bool:
    _, ext = os.path.splitext(filepath)
    if ext.lower() in extensions:
        return True
    basename = os.path.basename(filepath)
    return basename in extensions

def collect_files(root_dir: str, script_path: str, output_path: str,
                  extensions: Set[str]) -> Iterator[Tuple[str, str]]:
    """Yield (rel_path, full_path) for files to include."""
    root_dir = os.path.abspath(root_dir)
    script_path = os.path.abspath(script_path)
    output_path = os.path.abspath(output_path)

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if not should_exclude_directory(d)]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root_dir)
            # Normalize path separators to forward slashes for cross‑platform dumps
            rel_path = rel_path.replace('\\', '/')

            # Skip self and output file
            if same_file(full_path, script_path):
                continue
            if same_file(full_path, output_path):
                continue

            # Skip if any parent directory is excluded
            if any(should_exclude_directory(part) for part in rel_path.split('/')):
                continue

            if not should_include_file(full_path, extensions):
                continue

            if not is_text_file(full_path):
                print(f"Skipping binary: {rel_path}", file=sys.stderr)
                continue

            yield rel_path, full_path

def run_collect(args):
    script_path = os.path.abspath(__file__)
    root_dir = os.path.abspath(args.root)
    output_path = os.path.join(root_dir, args.output)

    # Determine extensions
    extensions = set(args.extensions) if args.extensions else DEFAULT_EXTENSIONS.copy()
    if not args.no_default_extensions and args.extensions:
        extensions.update(DEFAULT_EXTENSIONS)

    print(f"Scanning root  : {root_dir}")
    print(f"Output file    : {output_path}")
    print(f"Extensions     : {len(extensions)} extensions")

    file_count = 0
    total_bytes = 0

    with open(output_path, 'w', encoding='utf-8') as outfile:
        for rel_path, full_path in collect_files(root_dir, script_path, output_path, extensions):
            file_count += 1
            print(f"  Adding: {rel_path}")

            outfile.write(f"\n\n{HEADER_SEP}\n")
            outfile.write(f"FILE: {rel_path}\n")
            outfile.write(f"{HEADER_SEP}\n\n")

            try:
                content = read_file_content(full_path)
                outfile.write(content)
                total_bytes += len(content.encode('utf-8'))
            except Exception as e:
                outfile.write(f"[ERROR reading file: {e}]\n")
                print(f"    Error: {e}", file=sys.stderr)

    print("\n" + "=" * 80)
    print(f"Done! Collected {file_count} files.")
    print(f"Output size: {total_bytes / 1024:.1f} KB")
    print(f"Output file: {output_path}")

# ----------------------------------------------------------------------
# RECONSTRUCT MODE
# ----------------------------------------------------------------------
def parse_dump_file(dump_path: str) -> Iterator[Tuple[str, str]]:
    """
    Yield (rel_path, content_str) using line‑by‑line state machine.
    Handles large files efficiently by reading line‑by‑line.
    """
    with open(dump_path, 'r', encoding='utf-8') as f:
        i = 0
        lines = f.readlines()  # May be memory intensive for huge dumps
        # Alternative: streaming, but we'll keep it simple with a warning.
        if len(lines) > 100000:
            print("Warning: Dump file is very large. Parsing may be slow.", file=sys.stderr)

    i = 0
    while i < len(lines):
        # Skip leading empty lines
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        if i >= len(lines):
            break

        # Look for header start
        line = lines[i].rstrip('\n')
        if line.strip() != HEADER_SEP:
            i += 1
            continue

        i += 1
        if i >= len(lines):
            break
        file_line = lines[i].strip()
        if not file_line.startswith("FILE: "):
            i += 1
            continue
        rel_path = file_line[6:].strip()

        i += 1
        if i >= len(lines):
            break
        close_line = lines[i].rstrip('\n')
        if close_line.strip() != HEADER_SEP:
            i += 1
            continue

        i += 1
        content_lines = []
        while i < len(lines):
            # Peek ahead: if we encounter a new header, stop
            if lines[i].rstrip('\n').strip() == HEADER_SEP:
                if i + 1 < len(lines) and lines[i+1].strip().startswith("FILE: "):
                    break
            content_lines.append(lines[i])
            i += 1

        content = "".join(content_lines).rstrip('\n')
        yield rel_path, content

def run_reconstruct(args):
    dump_path = args.dump_file
    if not os.path.isfile(dump_path):
        print(f"Error: Dump file not found: {dump_path}", file=sys.stderr)
        sys.exit(1)

    if args.output is None:
        dump_dir = os.path.dirname(os.path.abspath(dump_path))
        output_root = os.path.join(dump_dir, "restored")
    else:
        output_root = args.output

    if not args.dry_run:
        os.makedirs(output_root, exist_ok=True)

    # Pre‑scan for confirmation (collect files)
    files_to_create: List[Tuple[str, str, bool]] = []
    for rel_path, _ in parse_dump_file(dump_path):
        try:
            target = safe_path(output_root, rel_path)
            exists = os.path.exists(target) if not args.dry_run else False
            files_to_create.append((rel_path, target, exists))
        except ValueError as e:
            print(f"Security error: {e}", file=sys.stderr)

    if args.confirm:
        print("Files to be created/overwritten:")
        for rel_path, _, exists in files_to_create:
            status = "OVERWRITE" if exists else "CREATE"
            print(f"  {status}: {rel_path}")
        response = input("\nProceed? [y/N] ").strip().lower()
        if response not in ('y', 'yes'):
            print("Aborted.")
            sys.exit(0)

    created = overwritten = skipped = errors = 0

    for rel_path, content in parse_dump_file(dump_path):
        try:
            target_path = safe_path(output_root, rel_path)
        except ValueError as e:
            print(f"Security error: {e}", file=sys.stderr)
            errors += 1
            continue

        file_exists = os.path.exists(target_path)
        if file_exists and not args.force:
            print(f"Skipping (already exists): {rel_path}")
            skipped += 1
            continue

        if args.dry_run:
            action = "Would overwrite" if file_exists else "Would create"
            print(f"{action}: {rel_path}")
            if file_exists:
                overwritten += 1
            else:
                created += 1
            continue

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        try:
            file_bytes = content.encode('utf-8')
            # Preserve existing permissions if file exists, else default 0o644
            atomic_write(target_path, file_bytes)

            action = "Overwrote" if file_exists else "Created"
            if file_exists:
                overwritten += 1
            else:
                created += 1
            print(f"{action}: {rel_path}")

        except Exception as e:
            print(f"Error writing {rel_path}: {e}", file=sys.stderr)
            errors += 1

    print("\n" + "=" * 80)
    if args.dry_run:
        print("DRY RUN – No files were actually written.")
    print(f"Reconstruction complete.")
    print(f"  Created    : {created}")
    print(f"  Overwritten: {overwritten}")
    print(f"  Skipped    : {skipped}")
    if errors:
        print(f"  Errors     : {errors}")
    if not args.dry_run:
        print(f"Output directory: {os.path.abspath(output_root)}")

# ----------------------------------------------------------------------
# Command‑line Interface
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Collect or reconstruct project source code.",
        prog="code_compiler.py"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="sub-command")

    # ----- Collect -----
    collect_parser = subparsers.add_parser("collect", help="Collect code into a dump file")
    collect_parser.add_argument("-o", "--output", default="code_dump.txt",
                                help="Output filename (default: code_dump.txt)")
    collect_parser.add_argument("-e", "--extensions", nargs="+",
                                help="File extensions to include (e.g., .py .js .html)")
    collect_parser.add_argument("-r", "--root", default=os.path.dirname(os.path.abspath(__file__)),
                                help="Root directory to scan (default: script location)")
    collect_parser.add_argument("--no-default-extensions", action="store_true",
                                help="Use only extensions provided with -e")
    collect_parser.set_defaults(func=run_collect)

    # ----- Reconstruct -----
    recon_parser = subparsers.add_parser("reconstruct", help="Rebuild project from a dump file")
    recon_parser.add_argument("dump_file", help="Path to the dump file")
    recon_parser.add_argument("-o", "--output", help="Output directory (default: 'restored' next to dump)")
    recon_parser.add_argument("-f", "--force", action="store_true", help="Overwrite existing files")
    recon_parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    recon_parser.add_argument("--confirm", action="store_true", help="Ask for confirmation before writing")
    recon_parser.set_defaults(func=run_reconstruct)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()