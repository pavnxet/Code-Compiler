#!/usr/bin/env python3
"""
Code Compiler GUI – Beautiful Tkinter Frontend
==============================================

A user-friendly graphical interface for collecting and reconstructing
project source files using the code_compiler.py backend.

Usage:
    python code_compiler_gui.py

Made with 💖 by pavnxet
"""

import sys
import os
import threading
import queue
import argparse
from pathlib import Path

# Tkinter imports
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# Import the backend functions from the original script
try:
    from code_compiler import run_collect, run_reconstruct
except ImportError:
    messagebox.showerror(
        "Import Error",
        "Could not import code_compiler.py.\n"
        "Make sure it is in the same directory as this GUI script."
    )
    sys.exit(1)


# ----------------------------------------------------------------------
# Output redirection for capturing prints
# ----------------------------------------------------------------------
class QueueWriter:
    """File-like object that puts lines into a queue."""
    def __init__(self, queue, is_error=False):
        self.queue = queue
        self.is_error = is_error
        self.buffer = ""

    def write(self, text):
        if text:
            self.buffer += text
            if '\n' in self.buffer:
                lines = self.buffer.splitlines(True)
                self.buffer = ""
                for line in lines:
                    if line.endswith('\n'):
                        self.queue.put((line.rstrip('\n'), self.is_error))
                    else:
                        self.buffer = line

    def flush(self):
        if self.buffer:
            self.queue.put((self.buffer, self.is_error))
            self.buffer = ""

    def isatty(self):
        return False


# ----------------------------------------------------------------------
# Main GUI Application
# ----------------------------------------------------------------------
class CodeCompilerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Code Compiler – Collect & Reconstruct")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)

        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._configure_styles()

        # Output queue for thread-safe logging
        self.output_queue = queue.Queue()
        self.running = False

        self._create_widgets()
        self._process_queue()  # Start periodic queue check

    def _configure_styles(self):
        """Apply custom colors and fonts."""
        self.style.configure("TNotebook", background="#f0f0f0")
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TLabel", background="#f0f0f0", font=("Segoe UI", 10))
        self.style.configure("TButton", font=("Segoe UI", 10), padding=6)
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        self.style.configure("Status.TLabel", background="#e0e0e0", relief="sunken", padding=4)
        self.style.configure("Run.TButton", font=("Segoe UI", 11, "bold"), background="#4CAF50")

    def _create_widgets(self):
        """Build the main UI."""
        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        # Create tabs
        self.collect_tab = ttk.Frame(self.notebook)
        self.reconstruct_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.collect_tab, text="Collect")
        self.notebook.add(self.reconstruct_tab, text="Reconstruct")

        self._build_collect_tab()
        self._build_reconstruct_tab()

        # Log area (shared)
        log_frame = ttk.LabelFrame(self.root, text="Output Log", padding=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white"
        )
        self.log_text.pack(fill="both", expand=True)

        # Configure text tags for colors
        self.log_text.tag_config("stderr", foreground="#f48771")
        self.log_text.tag_config("stdout", foreground="#d4d4d4")
        self.log_text.tag_config("info", foreground="#6a9955")

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            style="Status.TLabel"
        )
        status_bar.pack(fill="x", padx=10, pady=(0, 10))

    def _build_collect_tab(self):
        """Widgets for the Collect tab."""
        frame = self.collect_tab
        frame.columnconfigure(1, weight=1)

        # Header
        header = ttk.Label(frame, text="Collect Source Files", style="Header.TLabel")
        header.grid(row=0, column=0, columnspan=3, pady=(15, 20), sticky="w", padx=20)

        # Root directory
        ttk.Label(frame, text="Root Directory:").grid(row=1, column=0, sticky="w", padx=20, pady=5)
        self.collect_root_var = tk.StringVar(value=os.path.dirname(os.path.abspath(__file__)))
        root_entry = ttk.Entry(frame, textvariable=self.collect_root_var, width=50)
        root_entry.grid(row=1, column=1, sticky="ew", padx=(5, 5), pady=5)
        ttk.Button(frame, text="Browse...", command=self._browse_collect_root).grid(row=1, column=2, padx=5, pady=5)

        # Output file
        ttk.Label(frame, text="Output File:").grid(row=2, column=0, sticky="w", padx=20, pady=5)
        self.collect_output_var = tk.StringVar(value="code_dump.txt")
        output_entry = ttk.Entry(frame, textvariable=self.collect_output_var, width=50)
        output_entry.grid(row=2, column=1, sticky="ew", padx=(5, 5), pady=5)
        ttk.Button(frame, text="Browse...", command=self._browse_collect_output).grid(row=2, column=2, padx=5, pady=5)

        # Extensions
        ttk.Label(frame, text="Extensions:").grid(row=3, column=0, sticky="w", padx=20, pady=5)
        self.collect_ext_var = tk.StringVar()
        ext_entry = ttk.Entry(frame, textvariable=self.collect_ext_var, width=50)
        ext_entry.grid(row=3, column=1, sticky="ew", padx=(5, 5), pady=5)
        ttk.Label(frame, text="e.g., .py .js .html", font=("Segoe UI", 8)).grid(row=3, column=2, padx=5, pady=5, sticky="w")

        # Options
        options_frame = ttk.Frame(frame)
        options_frame.grid(row=4, column=0, columnspan=3, pady=15, padx=20, sticky="w")

        self.use_default_ext_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Use default extensions",
            variable=self.use_default_ext_var
        ).pack(anchor="w", pady=2)

        self.no_default_ext_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame,
            text="Use ONLY extensions provided above (ignore defaults)",
            variable=self.no_default_ext_var
        ).pack(anchor="w", pady=2)

        # Run button
        self.collect_run_btn = ttk.Button(
            frame,
            text="▶ Collect",
            style="Run.TButton",
            command=self._run_collect_threaded
        )
        self.collect_run_btn.grid(row=5, column=0, columnspan=3, pady=20)

    def _build_reconstruct_tab(self):
        """Widgets for the Reconstruct tab."""
        frame = self.reconstruct_tab
        frame.columnconfigure(1, weight=1)

        # Header
        header = ttk.Label(frame, text="Reconstruct Project", style="Header.TLabel")
        header.grid(row=0, column=0, columnspan=3, pady=(15, 20), sticky="w", padx=20)

        # Dump file
        ttk.Label(frame, text="Dump File:").grid(row=1, column=0, sticky="w", padx=20, pady=5)
        self.recon_dump_var = tk.StringVar()
        dump_entry = ttk.Entry(frame, textvariable=self.recon_dump_var, width=50)
        dump_entry.grid(row=1, column=1, sticky="ew", padx=(5, 5), pady=5)
        ttk.Button(frame, text="Browse...", command=self._browse_recon_dump).grid(row=1, column=2, padx=5, pady=5)

        # Output directory
        ttk.Label(frame, text="Output Directory:").grid(row=2, column=0, sticky="w", padx=20, pady=5)
        self.recon_output_var = tk.StringVar()
        output_entry = ttk.Entry(frame, textvariable=self.recon_output_var, width=50)
        output_entry.grid(row=2, column=1, sticky="ew", padx=(5, 5), pady=5)
        ttk.Button(frame, text="Browse...", command=self._browse_recon_output).grid(row=2, column=2, padx=5, pady=5)
        ttk.Label(frame, text="(leave blank for 'restored' next to dump)", font=("Segoe UI", 8)).grid(
            row=3, column=1, padx=5, pady=(0,10), sticky="w"
        )

        # Options
        options_frame = ttk.Frame(frame)
        options_frame.grid(row=4, column=0, columnspan=3, pady=5, padx=20, sticky="w")

        self.recon_force_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame,
            text="Force overwrite existing files",
            variable=self.recon_force_var
        ).pack(anchor="w", pady=2)

        self.recon_dry_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame,
            text="Dry run (preview only, don't write files)",
            variable=self.recon_dry_run_var
        ).pack(anchor="w", pady=2)

        self.recon_confirm_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame,
            text="Ask for confirmation before writing",
            variable=self.recon_confirm_var
        ).pack(anchor="w", pady=2)

        # Run button
        self.recon_run_btn = ttk.Button(
            frame,
            text="▶ Reconstruct",
            style="Run.TButton",
            command=self._run_reconstruct_threaded
        )
        self.recon_run_btn.grid(row=5, column=0, columnspan=3, pady=20)

    # ------------------------------------------------------------------
    # Browse callbacks
    # ------------------------------------------------------------------
    def _browse_collect_root(self):
        path = filedialog.askdirectory(title="Select Root Directory")
        if path:
            self.collect_root_var.set(path)

    def _browse_collect_output(self):
        path = filedialog.asksaveasfilename(
            title="Save Output As",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.collect_output_var.set(path)

    def _browse_recon_dump(self):
        path = filedialog.askopenfilename(
            title="Select Dump File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.recon_dump_var.set(path)

    def _browse_recon_output(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.recon_output_var.set(path)

    # ------------------------------------------------------------------
    # Execution threading
    # ------------------------------------------------------------------
    def _run_collect_threaded(self):
        if self.running:
            messagebox.showwarning("Busy", "An operation is already running.")
            return
        self._clear_log()
        self._set_running(True)
        thread = threading.Thread(target=self._run_collect, daemon=True)
        thread.start()

    def _run_reconstruct_threaded(self):
        if self.running:
            messagebox.showwarning("Busy", "An operation is already running.")
            return
        self._clear_log()
        self._set_running(True)
        thread = threading.Thread(target=self._run_reconstruct, daemon=True)
        thread.start()

    def _run_collect(self):
        """Called in background thread."""
        try:
            # Prepare arguments as argparse.Namespace
            args = argparse.Namespace()
            args.root = self.collect_root_var.get().strip()
            args.output = self.collect_output_var.get().strip()
            args.no_default_extensions = self.no_default_ext_var.get()

            ext_str = self.collect_ext_var.get().strip()
            if ext_str:
                args.extensions = ext_str.split()
            else:
                args.extensions = None

            # Redirect stdout/stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = QueueWriter(self.output_queue, is_error=False)
            sys.stderr = QueueWriter(self.output_queue, is_error=True)

            try:
                run_collect(args)
            except Exception as e:
                print(f"\nERROR: {e}", file=sys.stderr)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        except Exception as e:
            self.output_queue.put((f"Fatal error: {e}", True))
        finally:
            self.root.after(0, self._set_running, False)

    def _run_reconstruct(self):
        """Called in background thread."""
        try:
            args = argparse.Namespace()
            args.dump_file = self.recon_dump_var.get().strip()
            args.output = self.recon_output_var.get().strip() or None
            args.force = self.recon_force_var.get()
            args.dry_run = self.recon_dry_run_var.get()
            args.confirm = self.recon_confirm_var.get()

            # Redirect stdout/stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = QueueWriter(self.output_queue, is_error=False)
            sys.stderr = QueueWriter(self.output_queue, is_error=True)

            try:
                # For confirm prompt, we need to handle it via GUI.
                # The original script uses input(). We'll monkey-patch input
                # to use a tkinter dialog in the main thread.
                if args.confirm:
                    original_input = __builtins__.input
                    def gui_input(prompt=""):
                        # Must run in main thread, so we use a queue to communicate.
                        response_queue = queue.Queue()
                        self.root.after(0, lambda: response_queue.put(
                            self._ask_confirm(prompt) if args.confirm else "y"
                        ))
                        return response_queue.get()
                    __builtins__.input = gui_input
                else:
                    # If not confirm, disable input just in case.
                    __builtins__.input = lambda _="": "y"

                run_reconstruct(args)
            except Exception as e:
                print(f"\nERROR: {e}", file=sys.stderr)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                __builtins__.input = original_input if 'original_input' in locals() else input

        except Exception as e:
            self.output_queue.put((f"Fatal error: {e}", True))
        finally:
            self.root.after(0, self._set_running, False)

    def _ask_confirm(self, prompt):
        """Show a Yes/No dialog for confirmation."""
        return messagebox.askyesno("Confirm", prompt)

    def _set_running(self, running):
        self.running = running
        if running:
            self.status_var.set("Running...")
            self.collect_run_btn.config(state="disabled")
            self.recon_run_btn.config(state="disabled")
        else:
            self.status_var.set("Ready")
            self.collect_run_btn.config(state="normal")
            self.recon_run_btn.config(state="normal")

    def _clear_log(self):
        self.log_text.delete(1.0, tk.END)

    def _process_queue(self):
        """Poll the queue and update the log widget."""
        try:
            while True:
                msg, is_error = self.output_queue.get_nowait()
                self._append_log(msg, is_error)
        except queue.Empty:
            pass
        self.root.after(100, self._process_queue)

    def _append_log(self, msg, is_error=False):
        """Insert text into log with appropriate styling."""
        self.log_text.insert(tk.END, msg + "\n", "stderr" if is_error else "stdout")
        self.log_text.see(tk.END)


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def main():
    root = tk.Tk()
    app = CodeCompilerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()