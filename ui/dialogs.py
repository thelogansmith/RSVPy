"""
Reusable modal dialogs.

Phase 2 introduces two user-facing dialogs - file-changed prompt and
restart confirmation - both of which need the same structural plumbing
(modal Toplevel, keyboard navigation, focus, centered on parent). Rather
than copy-paste that into two one-off functions, _ModalBase handles it
and the top-level helpers just populate the body.

Each helper blocks until the user dismisses the dialog, then returns a
plain string indicating which action was chosen. String returns beat
booleans here because some dialogs (restart confirm, step 3) have three
outcomes, and "return 'cancel' / 'restart' / 'restart_no_ask'" reads
better than a bool plus a flag.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from ui.theme import Theme


class _ModalBase:
    """Boilerplate for a modal Toplevel dialog.

    Subclasses populate self.body with their content and call
    self.show() to block until the user dismisses it.
    """

    # Subclasses set this before calling show() to indicate the result.
    _result: str = ""

    def __init__(self, parent: tk.Misc, title: str, theme: Theme) -> None:
        self._theme = theme
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.resizable(False, False)
        self.top.config(bg=theme.background)

        # Make this a true modal: owner relationship + input grab.
        # transient() ties the dialog's lifecycle to the parent window
        # (minimize together, stay on top). grab_set() routes all events
        # to this window until it closes.
        self.top.transient(parent)

        # Escape dismisses with the default "cancel" outcome. Subclasses
        # that want Escape to mean something else can override _on_cancel.
        self.top.bind("<Escape>", lambda _e: self._on_cancel())
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Body frame - subclass populates this.
        self.body = tk.Frame(self.top, bg=theme.background, padx=18, pady=16)
        self.body.pack(fill="both", expand=True)

        # Button row - subclass populates via _add_button.
        self.button_row = tk.Frame(self.top, bg=theme.background,
                                    padx=18, pady=(0, 14))
        self.button_row.pack(fill="x")

    def _add_button(self, text: str, command: Callable[[], None],
                    default: bool = False) -> tk.Button:
        """Add a button to the button row. `default` highlights it."""
        btn = tk.Button(self.button_row, text=text, command=command, width=12)
        if default:
            btn.config(default="active")
        btn.pack(side="right", padx=(6, 0))
        return btn

    def _center_on_parent(self) -> None:
        """Position the dialog over the center of its parent window."""
        self.top.update_idletasks()
        parent = self.top.master
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        dw = self.top.winfo_width()
        dh = self.top.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 3  # Biased slightly above center, reads better.
        self.top.geometry(f"+{x}+{y}")

    def _on_cancel(self) -> None:
        """Default cancel behavior. Subclasses override as needed."""
        self._result = "cancel"
        self.top.destroy()

    def show(self) -> str:
        """Display the dialog and block until it's dismissed.

        Must be called after self.body and buttons are populated.
        """
        self._center_on_parent()
        # grab_set() must be called after the window is visible, hence
        # the update_idletasks in _center_on_parent above.
        self.top.grab_set()
        self.top.focus_set()
        self.top.wait_window()
        return self._result


def ask_file_changed(parent: tk.Misc, theme: Theme, filename: str,
                     progress_percent: int) -> str:
    """Prompt the user that a file has changed since they last read it.

    Returns "restart" (start at token 0) or "resume" (keep saved position).
    Escape / window-close default to "restart" - matching the spec's
    "silently resuming on a changed file is the bug this feature fixes."
    """

    class FileChangedDialog(_ModalBase):

        def _on_cancel(self) -> None:
            # Escape defaults to "start over," matching the default
            # button on the dialog itself.
            self._result = "restart"
            self.top.destroy()

        def _choose(self, result: str) -> None:
            self._result = result
            self.top.destroy()

    dlg = FileChangedDialog(parent, "File changed", theme)

    # Message body.
    msg = tk.Label(
        dlg.body,
        text=f"{filename} has changed since you last read it.",
        font=("Helvetica", 11, "bold"),
        bg=theme.background, fg=theme.text,
        wraplength=360, justify="left", anchor="w",
    )
    msg.pack(fill="x", pady=(0, 6))

    detail = tk.Label(
        dlg.body,
        text=(f"Your saved position was at {progress_percent}%. "
              "Start from the beginning, or resume anyway?"),
        bg=theme.background, fg=theme.text_muted,
        wraplength=360, justify="left", anchor="w",
    )
    detail.pack(fill="x")

    # Buttons. "Start over" is the default per spec.
    dlg._add_button("Resume anyway",
                    command=lambda: dlg._choose("resume"))
    default_btn = dlg._add_button("Start over",
                                   command=lambda: dlg._choose("restart"),
                                   default=True)
    # Return from the default button activates it.
    dlg.top.bind("<Return>", lambda _e: dlg._choose("restart"))
    default_btn.focus_set()

    return dlg.show()
