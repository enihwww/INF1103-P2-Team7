"""Entry point: `python main.py` starts the CLI, `python main.py --gui` starts the web GUI."""
from __future__ import annotations

import sys

from clubfund_app import ClubFundApp
from command_line_app import CommandLineApp
from io_manager import ConsoleIO


class Launcher:
    """Starts either the command-line menu or the GUI."""

    def __init__(self, arguments: list[str]) -> None:
        self._use_gui = "--gui" in arguments

    def run(self) -> None:
        io = ConsoleIO()
        app, warning, error = ClubFundApp.create()

        if warning:
            io.show_message(warning)

        if error or app is None:
            io.show_message(error or "ClubFund could not start.")
            return

        if self._use_gui:
            # Imported here so the CLI and tests do not need Flask.
            from gui_manager import WebGUI
            WebGUI(app).run()
        else:
            CommandLineApp(app, io).run()


if __name__ == "__main__":
    Launcher(sys.argv[1:]).run()
