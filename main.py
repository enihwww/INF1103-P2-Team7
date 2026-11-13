import sys

from clubfund_app import ClubFundApp
from io_manager import ConsoleIO


class CommandLineApp:
    """Runs the ClubFund menu in the terminal."""

    def __init__(self, app, io):
        self._app = app
        self._io = io
        # Map each menu number to the method that handles it.
        self._actions = {
            1: self._new_request,
            2: self._view_requests,
            3: self._view_budget,
            4: self._view_summary,
            5: self._export_excel,
            6: self._update_policy,
        }

    def run(self):
        while True:
            role = self._io.get_user_role()
            self._io.show_menu(role)
            choice = self._io.get_choice(role)

            # 7. Exit
            if choice == 7:
                self._io.show_message("Goodbye.")
                break

            self._actions[choice]()

    # 1. New funding request
    def _new_request(self):
        data = self._app.data_manager
        request = self._io.collect_request(self._app.new_request_id(), data.get_club_names())
        record, ai_error, save_error = self._app.process_request(request)

        if save_error:
            self._io.show_message(save_error)
            return

        if ai_error:
            self._io.show_message("\nAI service was unavailable. ")

        self._io.show_result(record)

    # 2. View all requests
    def _view_requests(self):
        self._io.show_requests(self._app.data_manager.records, "All Requests")

    # 3. View club annual budget
    def _view_budget(self):
        data = self._app.data_manager
        club_name = self._io.choose_budget_club(data.get_club_names())
        year = self._io.get_year()
        self._io.show_budget(data.get_budget_info(club_name, year), club_name, year)

    # 4. View summary
    def _view_summary(self):
        self._io.show_summary(self._app.data_manager.build_summary())

    # 5. Export Excel report
    def _export_excel(self):
        success, message = self._app.data_manager.export_to_excel()
        self._io.show_message(message)

    # 6. Update funding policy (new feature)
    def _update_policy(self):
        changes = self._io.get_policy_changes(self._app.data_manager.policy)

        if not changes:
            self._io.show_message("No changes made.")
            return

        success, message = self._app.update_policy(changes)
        self._io.show_message(message)

        if success:
            self._io.show_policy(self._app.data_manager.policy)

