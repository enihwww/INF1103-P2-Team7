from __future__ import annotations

import sys
from typing import Callable

from clubfund_app import ClubFundApp
from io_manager import ConsoleIO

MAX_PASSWORD_ATTEMPTS = 3


class CommandLineApp:
    """Runs the ClubFund menu in the terminal."""

    def __init__(self, app: ClubFundApp, io: ConsoleIO) -> None:
        self._app = app
        self._io = io
        self._club: str | None = None  # set when a student logs in
        # Each role has its own menu: (label, method that handles it).
        self._menus: dict[str, list[tuple[str, Callable[[], None]]]] = {
            "student": [
                ("New funding request", self._new_request),
                ("View my club's requests", self._view_requests),
                ("View my club's budget", self._view_budget),
            ],
            "admin": [
                ("View all requests", self._view_requests),
                ("View club annual budget", self._view_budget),
                ("View summary", self._view_summary),
                ("Export Excel report", self._export_excel),
                ("Update funding policy", self._update_policy),
            ],
        }

    def run(self) -> None:
        while True:
            role = self._io.get_user_role()

            if role is None:
                self._io.show_message("Goodbye.")
                break

            # Admins need the password; students choose their club once.
            self._club = None
            if role == "admin" and not self._admin_login():
                continue
            if role == "student":
                self._club = self._io.select_club(self._app.data_manager.get_club_names())

            self._run_menu(role)

    def _admin_login(self) -> bool:
        # Three tries, then back to the log-in menu.
        for attempt in range(MAX_PASSWORD_ATTEMPTS, 0, -1):
            if self._app.check_admin_password(self._io.get_password("Admin password: ")):
                return True
            self._io.show_message(f"Incorrect password. {attempt - 1} attempt(s) left.")
        return False

    def _run_menu(self, role: str) -> None:
        options = self._menus[role]
        labels = [label for label, _ in options] + ["Log out"]
        title = f"CLUBFUND - {self._club}" if self._club else "CLUBFUND - ADMIN"

        while True:
            self._io.show_menu(title, labels)
            choice = self._io.get_choice(len(labels))

            if choice == len(labels):
                return

            options[choice - 1][1]()

    # New funding request (students, for their own club)
    def _new_request(self) -> None:
        if self._club is None:
            return

        request = self._io.collect_request(self._app.new_request_id(), self._club)
        record, ai_error, save_error = self._app.process_request(request)

        if record is None:
            self._io.show_message(save_error or "Could not save the request.")
            return

        if ai_error:
            self._io.show_message("\nAI service was unavailable. ")

        self._io.show_result(record)

    # View requests (admins: every club; students: their own club)
    def _view_requests(self) -> None:
        data = self._app.data_manager

        if self._club:
            self._io.show_requests(data.records_for_club(self._club), f"{self._club} Requests")
        else:
            self._io.show_requests(data.records, "All Requests")

    # View annual budget (admins choose a club; students see their own)
    def _view_budget(self) -> None:
        data = self._app.data_manager
        club_name = self._club or self._io.choose_budget_club(data.get_club_names())
        year = self._io.get_year()
        self._io.show_budget(data.get_budget_info(club_name, year), club_name, year)

    # View summary
    def _view_summary(self) -> None:
        self._io.show_summary(self._app.data_manager.build_summary())

    # Export Excel report
    def _export_excel(self) -> None:
        success, message = self._app.data_manager.export_to_excel()
        self._io.show_message(message)

    # Update funding policy (new feature)
    def _update_policy(self) -> None:
        changes = self._io.get_policy_changes(self._app.data_manager.policy)

        if not changes:
            self._io.show_message("No changes made.")
            return

        success, message = self._app.update_policy(changes)
        self._io.show_message(message)

        if success:
            self._io.show_policy(self._app.data_manager.policy)


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
