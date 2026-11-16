"""Automated tests for ClubFund. Run with: python -m unittest -v

No live AI API is needed: stub classifiers return sample responses or raise errors.
"""
import copy
import json
import os
import shutil
import tempfile
import unittest
from importlib.util import find_spec

from ai_manager import AIClassifier, AIManager, FallbackClassifier, OpenAIClassifier, ResponseValidator
from clubfund_app import ClubFundApp
from data_manager import BudgetLedger, DataManager, JsonPolicyRepository, JsonRequestRepository
from logic_manager import (BusinessRule, CategoryLimitRule, FoodLimitRule, LogicManager,
                           PrizeLimitRule, RuleContext)
from models import (LOCKED_RULES, RULE_NAMES, Assessment, Check, FundingRecord, FundingRequest,
                    Policy, PolicyError)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

with open(os.path.join(DATA_DIR, "test_cases.json"), encoding="utf-8") as case_file:
    TEST_CASES = json.load(case_file)

DEFAULT_POLICY = {
    "max_request_amount": 1200.0, "minimum_lead_days": 14, "food_per_person_limit": 5.0,
    "max_prize_amount": 200.0, "equipment_quote_threshold": 300.0,
    "ineligible_categories": ["decoration"], "disabled_rules": [],
}
BUDGET_INFO = {"annual_budget": 1000.0, "used_budget": 0.0, "remaining_budget": 1000.0}


def make_request(expenses, participants=40, event_date="2026-11-20", submission_date="2026-11-01",
                 request_id="T1"):
    request = FundingRequest(request_id, "Computing Club", "Tech event", "A workshop",
                             event_date, submission_date, participants)
    for description, amount, quote in expenses:
        request.add_expense(description, amount, quote)
    return request


def make_ai_result(categories, event_type="workshop"):
    return {
        "event_type": event_type, "event_purpose": "Test event.",
        "expenses": [{"expense_id": f"E{number}", "category": category, "purpose": "Test.",
                      "ambiguous": False} for number, category in enumerate(categories, start=1)],
        "missing_information": [],
    }


class StubClassifier(AIClassifier):
    """Returns a fixed response or raises a fixed error, and counts calls."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    def classify(self, request):
        self.calls += 1
        if self.error:
            raise self.error
        return copy.deepcopy(self.response)


class TempDataMixin:
    """Gives each test its own copy of the data folder."""

    def setUp(self):
        self.data_dir = tempfile.mkdtemp()
        for name in ["policy.json", "club_budgets.json"]:
            shutil.copy(os.path.join(DATA_DIR, name), self.data_dir)

    def tearDown(self):
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def path(self, name):
        return os.path.join(self.data_dir, name)

    @staticmethod
    def submit(app, expenses):
        """Process a request with the next real ID (CF0001, CF0002...)."""
        return app.process_request(make_request(expenses, request_id=app.new_request_id()))


class TestModels(unittest.TestCase):

    def test_request_owns_numbered_expenses(self):
        request = make_request([("Food", 100, False), ("Prize", 50.5, True)])
        self.assertEqual([e.expense_id for e in request.expenses], ["E1", "E2"])
        self.assertEqual(request.total_amount(), 150.5)
        self.assertEqual(request.funding_year, 2026)
        self.assertEqual(request.lead_days(), 19)

    def test_expense_list_cannot_be_changed_from_outside(self):
        request = make_request([("Food", 100, False)])
        request.expenses.clear()
        self.assertEqual(len(request.expenses), 1)

    def test_saved_requests_round_trip_unchanged(self):
        with open(os.path.join(DATA_DIR, "requests.json"), encoding="utf-8") as file:
            raw = json.load(file)
        records = [FundingRecord.from_dict(item) for item in raw]
        self.assertEqual([record.to_dict() for record in records], raw)


class TestPolicy(unittest.TestCase):

    def test_missing_field_is_reported(self):
        data = dict(DEFAULT_POLICY)
        del data["max_prize_amount"]
        with self.assertRaisesRegex(PolicyError, "Policy is missing: max_prize_amount"):
            Policy.from_dict(data)

    def test_valid_update(self):
        policy = Policy.from_dict(DEFAULT_POLICY)
        policy.update({"max_prize_amount": 300, "ineligible_categories": ["decoration", "venue"]})
        self.assertEqual(policy.max_prize_amount, 300.0)
        self.assertEqual(policy.ineligible_categories, ["decoration", "venue"])

    def test_invalid_update_changes_nothing(self):
        policy = Policy.from_dict(DEFAULT_POLICY)
        invalid_changes = [
            {"max_request_amount": -1},
            {"minimum_lead_days": 2.5},
            {"food_per_person_limit": "five"},
            {"max_prize_amount": float("inf")},
            {"ineligible_categories": ["parties"]},
            {"unknown_field": 1},
            {"max_prize_amount": 999, "minimum_lead_days": -3},
            {"disabled_rules": ["no_such_rule"]},
            {"disabled_rules": ["unclear_information"]},
            {"disabled_rules": "food_limit"},
        ]
        for changes in invalid_changes:
            with self.subTest(changes=changes):
                with self.assertRaises(PolicyError):
                    policy.update(changes)
                self.assertEqual(policy.to_dict(), DEFAULT_POLICY)


    def test_part1_policy_file_without_rule_settings_loads(self):
        data = {k: v for k, v in DEFAULT_POLICY.items() if k != "disabled_rules"}
        policy = Policy.from_dict(data)
        self.assertTrue(all(policy.is_rule_enabled(rule_id) for rule_id in RULE_NAMES))


class TestBusinessRules(unittest.TestCase):

    def setUp(self):
        self.policy = Policy.from_dict(DEFAULT_POLICY)
        self.logic = LogicManager(self.policy, LogicManager.default_rules())

    def assess(self, request, ai_result, budget_info=BUDGET_INFO):
        return self.logic.assess_request(request, ai_result, budget_info)

    def test_cases_from_json(self):
        for case in TEST_CASES:
            with self.subTest(case=case["name"]):
                records = [FundingRecord.from_dict(item) for item in case["existing_records"]]
                budget_info = BudgetLedger({"Computing Club": 1000.0}, records).get_budget_info(
                    "Computing Club", 2026)
                assessment = self.assess(FundingRequest.from_dict(case["request"]),
                                         case["ai_result"], budget_info)
                for field, expected in case["expected"].items():
                    self.assertEqual(assessment.to_dict()[field], expected)

    def test_late_submission_needs_revision(self):
        request = make_request([("Snacks", 50, False)], submission_date="2026-11-10")
        assessment = self.assess(request, make_ai_result(["food"]))
        self.assertEqual(assessment.status, Assessment.REVISION)
        self.assertIn("Only 10 day(s) of lead time.", [c.message for c in assessment.checks])

    def test_single_request_limit(self):
        request = make_request([("Venue", 1300, False)])
        assessment = self.assess(request, make_ai_result(["venue"]),
                                 {"annual_budget": 5000.0, "used_budget": 0.0, "remaining_budget": 5000.0})
        self.assertEqual(assessment.status, Assessment.REVISION)
        self.assertEqual(assessment.estimated_eligible_amount, 1200.0)

    def test_equipment_quote_rule_uses_ai_category_amount_and_quote(self):
        rows = [("Camera", 300, False), ("Tripod", 300, True), ("Banner", 300, False)]
        assessment = self.assess(make_request(rows), make_ai_result(
            ["reusable_equipment", "reusable_equipment", "marketing"]),
            {"annual_budget": 5000.0, "used_budget": 0.0, "remaining_budget": 5000.0})
        self.assertEqual(assessment.issues, ["E1 requires a supplier quote."])

    def test_prize_limit_only_applies_to_competitions(self):
        request = make_request([("Vouchers", 300, False)])
        workshop = self.assess(request, make_ai_result(["prize"], "workshop"))
        competition = self.assess(request, make_ai_result(["prize"], "competition"))
        self.assertEqual(workshop.status, Assessment.READY)
        self.assertEqual(competition.status, Assessment.REVISION)
        self.assertEqual(competition.estimated_eligible_amount, 200.0)

    def test_food_limit_uses_participants(self):
        request = make_request([("Pizza", 120, False)], participants=20)
        assessment = self.assess(request, make_ai_result(["food"]))
        self.assertIn("Food exceeds the allowed amount by $20.00.", assessment.issues)
        self.assertEqual(assessment.estimated_eligible_amount, 100.0)

    def test_expense_missing_from_ai_goes_to_manual_review(self):
        request = make_request([("Food", 50, False), ("Mystery", 20, False)])
        assessment = self.assess(request, make_ai_result(["food"]))
        self.assertEqual(assessment.status, Assessment.MANUAL)
        self.assertEqual(assessment.budget_to_commit, 0.0)

    def test_checks_keep_phase1_order(self):
        request = make_request([("Food", 100, False), ("Vouchers", 150, False)])
        assessment = self.assess(request, make_ai_result(["food", "prize"], "competition"))
        self.assertEqual([c.message for c in assessment.checks], [
            "Request is within the single-request limit.",
            "$1000.00 is available before this request.",
            "19 day(s) of lead time.",
            "Food spending is within the limit.",
            "No prize-limit problem.",
        ])

    def test_every_rule_returns_a_non_negative_deduction(self):
        # LSP: any BusinessRule can be used in the same loop.
        request = make_request([("Food", 500, False), ("Decor", 50, False), ("Prize", 400, False)])
        ai_result = make_ai_result(["food", "decoration", "prize"], "competition")
        context = RuleContext(request, ai_result, self.policy, BUDGET_INFO)
        for rule in LogicManager.default_rules():
            with self.subTest(rule=type(rule).__name__):
                self.assertIsInstance(rule, BusinessRule)
                self.assertGreaterEqual(rule.evaluate(context, Assessment(2026, 0, 0, 0, 0, 0)), 0)

    def test_category_limit_rules_share_base_class(self):
        self.assertTrue(issubclass(FoodLimitRule, CategoryLimitRule))
        self.assertTrue(issubclass(PrizeLimitRule, CategoryLimitRule))
        with self.assertRaises(TypeError):
            CategoryLimitRule()  # abstract

    def test_new_rule_can_be_added_without_changing_logic_manager(self):
        # OCP: a new rule is plugged in through the constructor.
        class AlwaysReviewRule(BusinessRule):
            def evaluate(self, context, assessment):
                assessment.add_check(Check.REVIEW, "Extra rule.")
                return 0.0

        logic = LogicManager(self.policy, LogicManager.default_rules() + [AlwaysReviewRule()])
        assessment = logic.assess_request(make_request([("Food", 10, False)]), make_ai_result(["food"]), BUDGET_INFO)
        self.assertEqual(assessment.status, Assessment.MANUAL)

    def test_every_rule_has_a_known_id(self):
        ids = [rule.rule_id for rule in LogicManager.default_rules()]
        self.assertEqual(sorted(ids), sorted(RULE_NAMES))

    def test_disabled_rule_is_skipped(self):
        request = make_request([("Pizza", 300, False)], participants=20)
        self.policy.update({"disabled_rules": ["food_limit"]})
        assessment = self.assess(request, make_ai_result(["food"]))
        self.assertEqual(assessment.status, Assessment.READY)
        self.assertEqual(assessment.estimated_eligible_amount, 300.0)
        self.assertIn((Check.SKIPPED, "Food per-person limit rule is turned off by an admin."),
                      [(c.result, c.message) for c in assessment.checks])

    def test_disabled_request_limit_also_removes_its_cap(self):
        budget = {"annual_budget": 5000.0, "used_budget": 0.0, "remaining_budget": 5000.0}
        request = make_request([("Venue", 1500, False)])
        self.assertEqual(self.assess(request, make_ai_result(["venue"]), budget).estimated_eligible_amount, 1200.0)
        self.policy.update({"disabled_rules": ["request_limit"]})
        assessment = self.assess(request, make_ai_result(["venue"]), budget)
        self.assertEqual((assessment.status, assessment.estimated_eligible_amount), (Assessment.READY, 1500.0))

    def test_unclear_information_rule_cannot_be_turned_off(self):
        self.assertIn("unclear_information", LOCKED_RULES)
        with self.assertRaises(PolicyError):
            self.policy.update({"disabled_rules": ["unclear_information"]})

    def test_policy_change_is_used_by_next_assessment(self):
        request = make_request([("Vouchers", 250, False)])
        ai_result = make_ai_result(["prize"], "competition")
        self.assertEqual(self.assess(request, ai_result).status, Assessment.REVISION)
        self.policy.update({"max_prize_amount": 300})
        self.assertEqual(self.assess(request, ai_result).status, Assessment.READY)


class TestAIManager(unittest.TestCase):

    def setUp(self):
        self.request = make_request([("Food", 100, False), ("Vouchers", 150, False)])
        self.good = make_ai_result(["food", "prize"], "competition")

    def test_valid_response_is_used(self):
        stub = StubClassifier(self.good)
        result, error = AIManager(stub).analyse_request(self.request)
        self.assertIsNone(error)
        self.assertEqual(result, self.good)
        self.assertEqual(stub.calls, 1)

    def test_validator_rejects_malformed_responses(self):
        validator = ResponseValidator()
        bad_responses = {
            "not an object": [],
            "missing field": {k: v for k, v in self.good.items() if k != "event_purpose"},
            "bad event type": dict(self.good, event_type="party"),
            "bad category": make_ai_result(["food", "snacks"]),
            "duplicate id": dict(self.good, expenses=[self.good["expenses"][0]] * 2),
            "missing id": dict(self.good, expenses=self.good["expenses"][:1]),
            "ambiguous not bool": dict(self.good, expenses=[dict(e, ambiguous="no") for e in self.good["expenses"]]),
            "missing info not text": dict(self.good, missing_information=[1]),
        }
        for name, response in bad_responses.items():
            with self.subTest(name):
                valid, message = validator.validate(response, self.request)
                self.assertFalse(valid)
                self.assertTrue(message)

    def test_connection_failure_retries_then_falls_back(self):
        stub = StubClassifier(error=ConnectionError("Connection refused"))
        result, error = AIManager(stub).analyse_request(self.request)
        self.assertEqual(stub.calls, 3)
        self.assertEqual(error, "AI processing failed after 3 attempts: Connection refused")
        self.assertEqual(result["event_type"], "unknown")
        self.assertTrue(all(e["ambiguous"] for e in result["expenses"]))

    def test_invalid_schema_and_bad_json_fall_back(self):
        for stub in [StubClassifier(make_ai_result(["food"])),
                     StubClassifier(error=json.JSONDecodeError("Expecting value", "oops", 0)),
                     StubClassifier(error=TimeoutError("Request timed out."))]:
            with self.subTest(stub=stub.response or stub.error):
                result, error = AIManager(stub).analyse_request(self.request)
                self.assertIn("AI processing failed after 3 attempts", error)
                self.assertEqual(result, FallbackClassifier().classify(self.request))

    def test_classifiers_share_the_interface(self):
        # Polymorphism / LSP: the AI manager works with any AIClassifier.
        for classifier in [OpenAIClassifier(), FallbackClassifier(), StubClassifier(self.good)]:
            self.assertIsInstance(classifier, AIClassifier)

    def test_fallback_result_is_valid_and_needs_manual_review(self):
        result = FallbackClassifier().classify(self.request)
        self.assertEqual(ResponseValidator().validate(result, self.request), (True, ""))
        logic = LogicManager(Policy.from_dict(DEFAULT_POLICY), LogicManager.default_rules())
        self.assertEqual(logic.assess_request(self.request, result, BUDGET_INFO).status, Assessment.MANUAL)


class TestDataManager(TempDataMixin, unittest.TestCase):

    def test_missing_requests_file_starts_empty(self):
        records, error = JsonRequestRepository(self.path("requests.json")).load()
        self.assertEqual((records, error), ([], None))

    def test_corrupt_requests_file_is_reported(self):
        for content in ["{not json", '{"a": 1}', '["text"]']:
            with self.subTest(content=content):
                with open(self.path("requests.json"), "w", encoding="utf-8") as file:
                    file.write(content)
                records, error = JsonRequestRepository(self.path("requests.json")).load()
                self.assertEqual(records, [])
                self.assertIn("requests", error)

    def test_missing_or_corrupt_policy_is_reported(self):
        os.remove(self.path("policy.json"))
        self.assertEqual(JsonPolicyRepository(self.path("policy.json")).load(), (None, "policy.json was not found."))
        with open(self.path("policy.json"), "w", encoding="utf-8") as file:
            file.write("[]")
        policy, error = JsonPolicyRepository(self.path("policy.json")).load()
        self.assertIsNone(policy)
        self.assertTrue(error)

    def test_corrupt_budget_file_is_reported(self):
        with open(self.path("club_budgets.json"), "w", encoding="utf-8") as file:
            file.write('{"Computing Club": -5}')
        self.assertEqual(DataManager(self.data_dir).load_club_budgets(), "Invalid annual budget for Computing Club.")

    def test_records_persist_between_runs(self):
        first = self.make_app(StubClassifier(make_ai_result(["food"])))
        record, ai_error, save_error = self.submit(first, [("Snacks", 100, False)])
        self.assertIsNone(save_error)

        second = self.make_app(StubClassifier(make_ai_result(["food"])))
        self.assertEqual([r.to_dict() for r in second.data_manager.records], [record.to_dict()])
        self.assertEqual(second.new_request_id(), "CF0002")

    def test_only_ready_processed_requests_commit_budget(self):
        app = self.make_app(StubClassifier(make_ai_result(["food"])))
        ready, _, _ = self.submit(app, [("Snacks", 100, False)])
        self.assertTrue(ready.budget_committed)
        self.assertEqual(app.data_manager.get_budget_info("Computing Club", 2026)["remaining_budget"], 900.0)

        failed_app = self.make_app(StubClassifier(error=ConnectionError("offline")))
        failed, ai_error, _ = self.submit(failed_app, [("Snacks", 100, False)])
        self.assertEqual(failed.processing_status, FundingRecord.AI_FAILED)
        self.assertFalse(failed.budget_committed)
        self.assertEqual(failed_app.data_manager.build_summary()["ai_failed"], 1)

    def test_excel_export_creates_file(self):
        app = self.make_app(StubClassifier(make_ai_result(["food"])))
        self.submit(app, [("Snacks", 100, False)])
        success, message = app.data_manager.export_to_excel()
        self.assertTrue(success, message)
        self.assertTrue(os.path.exists(self.path("ClubFund_Report.xlsx")))

    def make_app(self, classifier):
        app, warning, error = ClubFundApp.create(self.data_dir, classifier)
        self.assertIsNone(error)
        return app


class TestPolicyUpdateFeature(TempDataMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.app, _, _ = ClubFundApp.create(self.data_dir, StubClassifier(make_ai_result(["prize"], "competition")))

    def read_policy_file(self):
        with open(self.path("policy.json"), encoding="utf-8") as file:
            return json.load(file)

    def test_update_is_saved_and_applied_to_new_requests(self):
        before, _, _ = self.submit(self.app, [("Vouchers", 250, False)])
        self.assertEqual(before.assessment.status, Assessment.REVISION)

        success, message = self.app.update_policy({"max_prize_amount": 250})
        self.assertTrue(success, message)
        self.assertEqual(self.read_policy_file()["max_prize_amount"], 250.0)

        after, _, _ = self.submit(self.app, [("Vouchers", 250, False)])
        self.assertEqual(after.assessment.status, Assessment.READY)
        # The earlier saved result is not recalculated.
        self.assertEqual(self.app.data_manager.find_record("CF0001").assessment.status, Assessment.REVISION)

    def test_invalid_update_is_not_saved(self):
        success, message = self.app.update_policy({"minimum_lead_days": -1})
        self.assertFalse(success)
        self.assertIn("minimum_lead_days", message)
        self.assertEqual(self.read_policy_file(), DEFAULT_POLICY)
        self.assertEqual(self.app.data_manager.policy.minimum_lead_days, 14)

    def test_save_failure_keeps_old_policy(self):
        os.remove(self.path("policy.json"))
        os.mkdir(self.path("policy.json"))  # a folder cannot be written as a file
        success, message = self.app.update_policy({"max_prize_amount": 500})
        self.assertFalse(success)
        self.assertIn("Could not save policy", message)
        self.assertEqual(self.app.data_manager.policy.max_prize_amount, 200.0)


@unittest.skipUnless(find_spec("flask"), "Flask is not installed")
class TestWebGUI(TempDataMixin, unittest.TestCase):

    def setUp(self):
        super().setUp()
        from gui_manager import WebGUI
        self.app, _, _ = ClubFundApp.create(self.data_dir, StubClassifier(make_ai_result(["food", "prize"], "competition")))
        flask_app = WebGUI(self.app, secret_key="test").flask_app
        flask_app.testing = True
        self.client = flask_app.test_client()

    def login(self, role, club="Computing Club", password="1234"):
        return self.client.post("/", data={"role": role, "club": club, "password": password})

    def submit_form(self, **changes):
        form = {"event_title": "Hackathon", "event_description": "Coding competition",
                "event_date": "2026-11-20", "submission_date": "2026-11-01", "expected_participants": "40",
                "description_1": "Food", "amount_1": "100", "description_2": "Vouchers", "amount_2": "150"}
        form.update(changes)
        return self.client.post("/requests/new", data=form, follow_redirects=True)

    def test_pages_need_login(self):
        self.assertIn("/", self.client.get("/requests").headers["Location"])

    def test_student_cannot_open_admin_pages(self):
        self.login("student")
        for path in ["/policy", "/summary", "/budget"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 302)

    def test_submit_request_through_gui(self):
        self.login("student")
        response = self.submit_form()
        self.assertIn(b"READY_FOR_REVIEW", response.data)
        self.assertEqual(self.app.data_manager.find_record("CF0001").request.total_amount(), 250.0)

    def test_admin_needs_the_password(self):
        for password in ["", "0000", "12345"]:
            with self.subTest(password=password):
                response = self.client.post("/", data={"role": "admin", "password": password}, follow_redirects=True)
                self.assertIn(b"Incorrect admin password.", response.data)
                self.assertEqual(self.client.get("/summary").status_code, 302)
        self.login("admin")
        self.assertEqual(self.client.get("/summary").status_code, 200)

    def test_admin_password_can_be_changed_by_environment(self):
        os.environ["CLUBFUND_ADMIN_PASSWORD"] = "s3cret"
        try:
            self.assertFalse(self.app.check_admin_password("1234"))
            self.assertTrue(self.app.check_admin_password("s3cret"))
        finally:
            del os.environ["CLUBFUND_ADMIN_PASSWORD"]

    def test_page_styles_are_well_formed(self):
        # A broken CSS rule once pushed every page below the sidebar.
        with open(os.path.join(BASE_DIR, "templates", "base.html"), encoding="utf-8") as file:
            css = file.read().split("<style>")[1].split("</style>")[0]
        self.assertEqual(css.count("{"), css.count("}"))
        self.assertIn(".layout { display: flex;", css)

    def test_student_pages_offer_no_admin_view(self):
        self.login("student")
        page = self.client.get("/requests").data
        self.assertNotIn(b"Admin View", page)
        self.assertIn(b"Log out", page)

    def test_student_must_choose_a_club(self):
        response = self.client.post("/", data={"role": "student", "club": ""}, follow_redirects=True)
        self.assertIn(b"Select your club", response.data)
        self.assertEqual(self.client.get("/requests").status_code, 302)

    def test_student_can_only_submit_for_own_club(self):
        self.login("student", "Sports Club")
        self.submit_form(club_name="Computing Club")  # a tampered form field is ignored
        self.assertEqual(self.app.data_manager.find_record("CF0001").club_name, "Sports Club")

    def test_student_only_sees_own_club(self):
        self.login("student", "Sports Club")
        self.submit_form(event_title="Sports day")
        self.login("student", "Computing Club")
        self.submit_form(event_title="Hackathon")
        page = self.client.get("/requests").data
        self.assertIn(b"CF0002", page)
        self.assertNotIn(b"CF0001", page)
        self.assertEqual(self.client.get("/requests/CF0001").status_code, 302)
        self.assertEqual(self.client.get("/requests/CF0002").status_code, 200)

    def test_admin_cannot_create_requests(self):
        self.login("admin")
        self.assertEqual(self.client.get("/requests/new").status_code, 302)
        self.submit_form()
        self.assertEqual(self.app.data_manager.records, [])
        self.assertNotIn(b"New Funding Request", self.client.get("/requests").data)

    def test_invalid_form_is_not_processed(self):
        self.login("student")
        response = self.client.post("/requests/new", data={"event_date": "20-11-2026", "description_1": "", "amount_1": "-5"})
        self.assertIn(b"Event date must be a valid date", response.data)
        self.assertIn(b"Expense 1: enter a valid amount", response.data)
        self.assertEqual(self.app.data_manager.records, [])

    def test_admin_updates_policy_through_gui(self):
        self.login("admin")
        form = {"max_request_amount": "1500", "minimum_lead_days": "7", "food_per_person_limit": "6",
                "max_prize_amount": "250", "equipment_quote_threshold": "300",
                "ineligible_categories": ["decoration", "venue"]}
        response = self.client.post("/policy", data=form, follow_redirects=True)
        self.assertIn(b"Funding policy updated.", response.data)
        policy = self.app.data_manager.policy
        self.assertEqual((policy.max_request_amount, policy.minimum_lead_days), (1500.0, 7))
        self.assertEqual(policy.ineligible_categories, ["decoration", "venue"])

    def test_admin_turns_rule_off_and_on_through_gui(self):
        self.login("admin")
        form = {"max_request_amount": "1200", "minimum_lead_days": "14", "food_per_person_limit": "5",
                "max_prize_amount": "200", "equipment_quote_threshold": "300",
                "ineligible_categories": ["decoration"], "rules_form": "1",
                "enabled_rules": [r for r in RULE_NAMES if r != "prize_limit"]}
        self.client.post("/policy", data=form)
        self.assertEqual(self.app.data_manager.policy.disabled_rules, ["prize_limit"])
        form["enabled_rules"] = list(RULE_NAMES)
        self.client.post("/policy", data=form)
        self.assertEqual(self.app.data_manager.policy.disabled_rules, [])

    def test_admin_policy_form_rejects_bad_numbers(self):
        self.login("admin")
        form = {"max_request_amount": "abc", "minimum_lead_days": "-2", "food_per_person_limit": "5",
                "max_prize_amount": "200", "equipment_quote_threshold": "300"}
        response = self.client.post("/policy", data=form, follow_redirects=True)
        self.assertIn(b"Max request amount must be a number.", response.data)
        self.assertEqual(self.app.data_manager.policy.to_dict(), DEFAULT_POLICY)

    def test_admin_pages_and_export(self):
        self.login("admin")
        self.assertEqual(self.client.get("/summary").status_code, 200)
        self.assertIn(b"$1000.00", self.client.get("/budget?club=Computing+Club&year=2026").data)
        response = self.client.post("/export")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        response.close()


if __name__ == "__main__":
    unittest.main()
