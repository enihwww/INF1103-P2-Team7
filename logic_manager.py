from datetime import date


# Add all expense amounts.
def calculate_total(expenses):
    total = 0

    for expense in expenses:
        total += expense["amount"]

    return round(total, 2)


# Add up the amounts of all expenses in one category.
def calculate_category_total(expenses, ai_expenses, category):
    total = 0

    for expense in expenses:
        expense_id = expense["expense_id"]

        if ai_expenses[expense_id]["category"] == category:
            total += expense["amount"]

    return round(total, 2)


# Return the number of days between submission and event.
def calculate_lead_days(submission_date, event_date):
    submitted = date.fromisoformat(submission_date)
    event = date.fromisoformat(event_date)

    return (event - submitted).days


# Store one PASS, FAIL or REVIEW message.
def add_check(checks, result, message):
    checks.append({
        "result": result,
        "message": message
    })


# Return True if any check has this result.
def has_result(checks, result):
    for check in checks:

        if check["result"] == result:
            return True

    return False


# Put AI results in a dictionary so they can be found by expense ID.
def build_ai_lookup(request, ai_result):
    ai_expenses = {}

    for ai_expense in ai_result["expenses"]:
        ai_expenses[
            ai_expense["expense_id"]
        ] = ai_expense

    # If an expense is missing, treat it as unknown.
    for expense in request["expenses"]:

        if expense["expense_id"] not in ai_expenses:
            ai_expenses[
                expense["expense_id"]
            ] = {
                "category": "unknown",
                "ambiguous": True
            }

    return ai_expenses


# Rule 1: Maximum amount allowed for one request.
def check_request_limit(
    total_requested,
    policy,
    checks,
    issues
):
    max_request = policy["max_request_amount"]

    if total_requested > max_request:
        issues.append(
            f"Total request exceeds the "
            f"${max_request:.2f} single-request limit."
        )

        add_check(
            checks,
            "FAIL",
            "Request is over the single-request limit."
        )

    else:
        add_check(
            checks,
            "PASS",
            "Request is within the single-request limit."
        )


# Rule 2: Club must have enough annual budget left.
def check_remaining_budget(
    total_requested,
    budget_info,
    checks,
    issues
):
    remaining_budget = budget_info["remaining_budget"]
    annual_budget = budget_info["annual_budget"]

    if total_requested > remaining_budget:
        shortfall = total_requested - remaining_budget

        issues.append(
            f"Request exceeds the remaining annual budget "
            f"by ${shortfall:.2f}."
        )

        add_check(
            checks,
            "FAIL",
            f"Only ${remaining_budget:.2f} left from the "
            f"${annual_budget:.2f} budget."
        )

    else:
        add_check(
            checks,
            "PASS",
            f"${remaining_budget:.2f} is available "
            "before this request."
        )


# Rule 3: Request must be submitted early enough.
def check_lead_time(
    lead_days,
    policy,
    checks,
    issues
):
    minimum_days = policy["minimum_lead_days"]

    if lead_days < minimum_days:
        issues.append(
            f"Request must be submitted at least "
            f"{minimum_days} days before the event."
        )

        add_check(
            checks,
            "FAIL",
            f"Only {lead_days} day(s) of lead time."
        )

    else:
        add_check(
            checks,
            "PASS",
            f"{lead_days} day(s) of lead time."
        )


# Rule 4: Missing or unclear AI information needs human review.
def check_unclear_information(
    request,
    ai_result,
    ai_expenses,
    checks,
    issues
):
    if ai_result["event_type"] == "unknown":
        issues.append(
            "Event type could not be classified."
        )

        add_check(
            checks,
            "REVIEW",
            "Event type needs human review."
        )

    if ai_result["missing_information"]:
        issues.append(
            "Missing information: "
            + ", ".join(
                ai_result["missing_information"]
            )
        )

        add_check(
            checks,
            "REVIEW",
            "Some request information is missing."
        )

    for expense in request["expenses"]:
        expense_id = expense["expense_id"]
        ai_expense = ai_expenses[expense_id]

        if (
            ai_expense["ambiguous"]
            or ai_expense["category"] == "unknown"
        ):
            issues.append(
                f"{expense_id} could not be classified clearly."
            )

            add_check(
                checks,
                "REVIEW",
                f"{expense_id} needs human review."
            )


# Rule 5: Some categories cannot be funded.
def check_ineligible_categories(
    request,
    ai_expenses,
    policy,
    checks,
    issues
):
    ineligible_categories = policy[
        "ineligible_categories"
    ]

    amount_removed = 0

    for expense in request["expenses"]:
        expense_id = expense["expense_id"]
        category = ai_expenses[
            expense_id
        ]["category"]

        if category in ineligible_categories:
            amount_removed += expense["amount"]

            issues.append(
                f"{expense_id} ({category}) is not fundable."
            )

            add_check(
                checks,
                "FAIL",
                f"{expense_id} ({category}) is not fundable."
            )

    return amount_removed


# Rule 6: Food must stay under the per-person limit.
def check_food_limit(
    request,
    ai_expenses,
    policy,
    checks,
    issues
):
    total_food = calculate_category_total(
        request["expenses"],
        ai_expenses,
        "food"
    )

    food_limit = (
        request["expected_participants"]
        * policy["food_per_person_limit"]
    )

    if total_food > food_limit:
        excess = total_food - food_limit

        issues.append(
            f"Food exceeds the allowed amount by "
            f"${excess:.2f}."
        )

        add_check(
            checks,
            "FAIL",
            f"Food limit is ${food_limit:.2f}."
        )

        return excess

    if total_food > 0:
        add_check(
            checks,
            "PASS",
            "Food spending is within the limit."
        )

    return 0


# Rule 7: Competitions have a prize limit.
def check_prize_limit(
    request,
    ai_result,
    ai_expenses,
    policy,
    checks,
    issues
):
    total_prizes = calculate_category_total(
        request["expenses"],
        ai_expenses,
        "prize"
    )

    prize_limit = policy["max_prize_amount"]

    if (
        ai_result["event_type"] == "competition"
        and total_prizes > prize_limit
    ):
        excess = total_prizes - prize_limit

        issues.append(
            f"Competition prizes exceed the limit by "
            f"${excess:.2f}."
        )

        add_check(
            checks,
            "FAIL",
            f"Competition prize limit is "
            f"${prize_limit:.2f}."
        )

        return excess

    if total_prizes > 0:
        add_check(
            checks,
            "PASS",
            "No prize-limit problem."
        )

    return 0


# Rule 8: Expensive reusable equipment needs a supplier quote.
def check_equipment_quotes(
    request,
    ai_expenses,
    policy,
    checks,
    issues
):
    quote_limit = policy[
        "equipment_quote_threshold"
    ]

    for expense in request["expenses"]:
        expense_id = expense["expense_id"]
        category = ai_expenses[
            expense_id
        ]["category"]

        if (
            category == "reusable_equipment"
            and expense["amount"] >= quote_limit
            and not expense["quote_available"]
        ):
            issues.append(
                f"{expense_id} requires a supplier quote."
            )

            add_check(
                checks,
                "FAIL",
                f"{expense_id} needs a quote "
                f"(${quote_limit:.2f} or more)."
            )


def decide_status(checks):
    if has_result(checks, "REVIEW"):
        return "MANUAL_REVIEW"

    if has_result(checks, "FAIL"):
        return "REVISION_REQUIRED"

    return "READY_FOR_REVIEW"


# Apply all ClubFund business rules to a request.
def assess_request(
    request,
    ai_result,
    policy,
    budget_info
):
    checks = []
    issues = []

    ai_expenses = build_ai_lookup(
        request,
        ai_result
    )

    total_requested = calculate_total(
        request["expenses"]
    )

    lead_days = calculate_lead_days(
        request["submission_date"],
        request["event_date"]
    )

    annual_budget = budget_info[
        "annual_budget"
    ]

    used_budget = budget_info[
        "used_budget"
    ]

    remaining_budget = budget_info[
        "remaining_budget"
    ]

    # Deterministic checks always run, even if AI is unavailable.
    check_request_limit(
        total_requested,
        policy,
        checks,
        issues
    )

    check_remaining_budget(
        total_requested,
        budget_info,
        checks,
        issues
    )

    check_lead_time(
        lead_days,
        policy,
        checks,
        issues
    )

    # AI-dependent checks use the validated AI result.
    # If the API failed, fallback values are unknown/ambiguous,
    # causing MANUAL_REVIEW rather than pretending AI succeeded.
    check_unclear_information(
        request,
        ai_result,
        ai_expenses,
        checks,
        issues
    )

    check_equipment_quotes(
        request,
        ai_expenses,
        policy,
        checks,
        issues
    )

    eligible_amount = total_requested

    eligible_amount -= check_ineligible_categories(
        request,
        ai_expenses,
        policy,
        checks,
        issues
    )

    eligible_amount -= check_food_limit(
        request,
        ai_expenses,
        policy,
        checks,
        issues
    )

    eligible_amount -= check_prize_limit(
        request,
        ai_result,
        ai_expenses,
        policy,
        checks,
        issues
    )

    # This is only a provisional value when AI processing failed,
    # because category-based rules could not be fully evaluated.
    eligible_amount = min(
        eligible_amount,
        total_requested,
        policy["max_request_amount"],
        remaining_budget
    )

    eligible_amount = round(
        max(0, eligible_amount),
        2
    )

    status = decide_status(checks)

    # Only successful, fully processed requests use annual budget.
    if status == "READY_FOR_REVIEW":
        budget_to_commit = eligible_amount
    else:
        budget_to_commit = 0.0

    remaining_after = round(
        max(
            0,
            remaining_budget - budget_to_commit
        ),
        2
    )

    return {
        "status": status,
        "funding_year": request["funding_year"],
        "annual_budget": annual_budget,
        "used_budget_before": used_budget,
        "remaining_budget_before": remaining_budget,
        "total_requested": total_requested,
        "estimated_eligible_amount": eligible_amount,
        "budget_to_commit": budget_to_commit,
        "remaining_budget_after": remaining_after,
        "lead_days": lead_days,
        "checks": checks,
        "issues": issues
    }

