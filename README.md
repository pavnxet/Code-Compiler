# Code Compiler

**Archive and restore entire codebases as a single portable text file.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.6+](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://www.python.org/)

`code_compiler.py` lets you archive an entire codebase into one portable text file, then later restore the exact folder structure and file contents from that archive. Perfect for:

- Sharing projects with LLMs (ChatGPT, DeepSeek, Claude) for code review or assistance.
- Creating snapshots for documentation or backup.
- Moving projects across environments without zipping.

---

## ✨ Features

- **Two-in-one tool** – Collect and reconstruct with a single script.
- **Recursive scanning** – Includes all subfolders automatically.
- **Configurable file types** – Choose which extensions to include (defaults cover most languages).
- **Safe reconstruction** – Path traversal protection + atomic writes to prevent corruption.
- **Dry‑run & confirmation** – Preview before writing files.
- **Skips binaries & common junk** – Ignores `node_modules`, `.git`, `__pycache__`, etc.
- **Cross‑platform** – Works on Windows, macOS, and Linux.

---

## 📦 Installation

No dependencies outside the Python standard library. Just download `code_compiler.py` and make sure you have **Python 3.6 or newer** installed.

```bash
# Clone the repository
git clone https://github.com/pavnxet/Code-Compiler.git
cd Code-Compiler

# (Optional) Make it executable on Unix-like systems
chmod +x code_compiler.py
