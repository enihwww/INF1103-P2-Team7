"""GUI Manager main file: holds WebGUI and imports its form classes."""
from __future__ import annotations

import os
import secrets
from datetime import date
from typing import TYPE_CHECKING, Any, Callable
from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from werkzeug.wrappers import Response

if TYPE_CHECKING:
    from clubfund_app import ClubFundApp

from models import FundingRecord, LOCKED_RULES, RULE_NAMES, VALID_CATEGORIES
from .gui_config import MAX_EXPENSES, TEMPLATE_DIR, XLSX_TYPE
from .policy_form import PolicyForm
from .request_form import RequestForm


class WebGUI:
    """Browser-based GUI for ClubFund (advanced feature).

    It only handles web input and output; all processing goes through ClubFundApp.
    """

    def __init__(self, app: ClubFundApp, secret_key: str | None = None) -> None:
        self._app = app
        # Templates sit in the project root, one folder above this package.
        self._flask = Flask(__name__, template_folder=TEMPLATE_DIR)
        self._flask.secret_key = secret_key or os.getenv("CLUBFUND_SECRET_KEY") or secrets.token_hex(16)
        self._register_routes()

    @property
    def flask_app(self) -> Flask:
        return self._flask

    def run(self) -> None:
        host = os.getenv("CLUBFUND_HOST", "127.0.0.1")
        port = int(os.getenv("CLUBFUND_PORT", "5000"))
        print(f"ClubFund GUI running at http://localhost:{port}  (Ctrl+C to stop)")
        # One request at a time, so two saves can never overlap.
        self._flask.run(host=host, port=port, debug=False, threaded=False)

    def _register_routes(self) -> None:
        routes: list[tuple[str, str, Callable[..., Response | str], list[str]]] = [
            ("/", "login", self.login, ["GET", "POST"]),
            ("/logout", "logout", self.logout, ["GET"]),
            ("/requests", "requests", self.view_requests, ["GET"]),
            ("/requests/new", "new_request", self.new_request, ["GET", "POST"]),
            ("/requests/<request_id>", "result", self.view_result, ["GET"]),
            ("/budget", "budget", self.view_budget, ["GET"]),
            ("/summary", "summary", self.view_summary, ["GET"]),
            ("/export", "export", self.export_excel, ["POST"]),
            ("/policy", "policy", self.update_policy, ["GET", "POST"]),
        ]
        for path, name, handler, methods in routes:
            self._flask.add_url_rule(path, name, handler, methods=methods)

    def _render(self, template: str, **values: Any) -> str:
        # The top bar shows whether an API key is set (otherwise requests use the fallback).
        return render_template(template, role=session.get("role"), my_club=session.get("club"),
                               ai_key_set=bool(os.getenv("OPENAI_API_KEY")), **values)

    def _not_allowed(self, admin_only: bool = False, student_only: bool = False) -> Response | None:
        """Return a redirect if the current role may not open this page."""
        role = session.get("role")
        if role is None:
            return redirect(url_for("login"))
        if admin_only and role != "admin":
            flash("This page is only available to admins.", "error")
            return redirect(url_for("requests"))
        if student_only and role != "student":
            flash("Admins cannot create funding requests. Log in as a student of the club.", "error")
            return redirect(url_for("requests"))
        return None

    def _can_see(self, record: FundingRecord) -> bool:
        """Students may only see their own club's requests."""
        return session.get("role") == "admin" or record.club_name == session.get("club")

    # Log in: Admin, or Student of one club (same roles as the CLI).
    def login(self) -> Response | str:
        clubs = self._app.data_manager.get_club_names()

        if request.method == "POST":
            role = request.form.get("role")
            club = request.form.get("club", "")

            if role == "admin" and self._app.check_admin_password(request.form.get("password", "")):
                session.clear()
                session["role"] = "admin"
                return redirect(url_for("requests"))

            if role == "student" and club in clubs:
                session.clear()
                session["role"] = "student"
                session["club"] = club
                return redirect(url_for("requests"))

            if role == "admin":
                flash("Incorrect admin password.", "error")
            elif role == "student":
                flash("Select your club to continue as a student.", "error")

        return self._render("login.html", clubs=clubs)

    def logout(self) -> Response:
        session.clear()
        return redirect(url_for("login"))

    # 1. New funding request (students only, for their own club)
    def new_request(self) -> Response | str:
        blocked = self._not_allowed(student_only=True)
        if blocked:
            return blocked

        data = self._app.data_manager
        form = RequestForm(request.form, data.get_club_names(), fixed_club=session["club"])

        if request.method == "POST":
            funding_request = form.to_request(self._app.new_request_id())

            if funding_request:
                record, ai_error, save_error = self._app.process_request(funding_request)

                if record is None:
                    flash(save_error or "Could not save the request.", "error")
                else:
                    # An AI failure is shown on the result page itself (AI status: UNAVAILABLE).
                    return redirect(url_for("result", request_id=record.request_id))

        return self._render("new_request.html", form=form.values(), errors=form.errors)

    # 2. View requests: admins see every club, students see their own club and its budget
    def view_requests(self) -> Response | str:
        blocked = self._not_allowed()
        if blocked:
            return blocked

        data = self._app.data_manager
        if session["role"] == "admin":
            return self._render("requests.html", records=data.records)

        year = request.args.get("year", "").strip()
        if not (year.isdigit() and len(year) == 4):
            year = str(date.today().year)
        return self._render("requests.html", records=data.records_for_club(session["club"]),
                            year=year, budget_info=data.get_budget_info(session["club"], int(year)))

    def view_result(self, request_id: str) -> Response | str:
        blocked = self._not_allowed()
        if blocked:
            return blocked

        record = self._app.data_manager.find_record(request_id)
        if record is None or not self._can_see(record):
            flash(f"Request {request_id} was not found.", "error")
            return redirect(url_for("requests"))

        ai_failed = record.processing_status == FundingRecord.AI_FAILED
        return self._render("result.html", record=record, ai_failed=ai_failed)

    # 3. View club annual budget
    def view_budget(self) -> Response | str:
        blocked = self._not_allowed(admin_only=True)
        if blocked:
            return blocked

        data = self._app.data_manager
        club = request.args.get("club", "")
        year = request.args.get("year", "").strip()
        budget_info = None

        if club or year:
            if club not in data.get_club_names():
                flash("Select a registered club.", "error")
            elif not (year.isdigit() and len(year) == 4):
                flash("Enter a valid four-digit year.", "error")
            else:
                budget_info = data.get_budget_info(club, int(year))

        return self._render("budget.html", clubs=data.get_club_names(), club=club,
                            year=year, budget_info=budget_info)

    # 4. View summary
    def view_summary(self) -> Response | str:
        blocked = self._not_allowed(admin_only=True)
        if blocked:
            return blocked
        return self._render("summary.html", summary=self._app.data_manager.build_summary())

    # 5. Export Excel report
    def export_excel(self) -> Response:
        blocked = self._not_allowed(admin_only=True)
        if blocked:
            return blocked

        data = self._app.data_manager
        success, message = data.export_to_excel()

        if not success:
            flash(message, "error")
            return redirect(url_for("summary"))
        return send_file(data.excel_file, as_attachment=True, mimetype=XLSX_TYPE)

    # 6. Update funding policy (new feature)
    def update_policy(self) -> Response | str:
        blocked = self._not_allowed(admin_only=True)
        if blocked:
            return blocked

        if request.method == "POST":
            form = PolicyForm(request.form)
            changes = form.to_changes()

            if changes is None:
                for error in form.errors:
                    flash(error, "error")
            else:
                success, message = self._app.update_policy(changes)
                flash(message, "success" if success else "error")
                if success:
                    return redirect(url_for("policy"))

        return self._render("policy.html", policy=self._app.data_manager.policy,
                            categories=sorted(VALID_CATEGORIES), label=PolicyForm.label,
                            rules=RULE_NAMES, locked=LOCKED_RULES)


__all__ = [
    "MAX_EXPENSES",
    "PolicyForm",
    "TEMPLATE_DIR",
    "RequestForm",
    "WebGUI",
    "XLSX_TYPE",
]
