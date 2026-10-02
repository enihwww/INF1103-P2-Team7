from datetime import date

#add all expense amounts
def calculate_total(expenses):
    return round(sum(expense["amount"] for expense in expenses), 2)

#return the number of days between submission and event
def calculate_lead_days(submission_date, event_date):
    submitted = date.fromisoformat(submission_date)
    event = date.fromisoformat(event_date)

    return (event - submitted).days

#store one PASS, FAIL or REVIEW message
def add_check(checks, result, message):
    checks.append({
        "result": result,
        "message": message
    })

#apply all ClubFund business rules to a request
def assess_request(request, ai_result, policy, budget_info):
    checks = []
    issues = []

    revision_needed = False
    manual_review_needed = False

    total_requested = calculate_total(request["expenses"])
    eligible_amount = total_requested

    #come from data_manager.get_budget_info()
    annual_budget = budget_info["annual_budget"]
    used_budget = budget_info["used_budget"]
    remaining_budget = budget_info["remaining_budget"]

    #easy to find the AI result for E1, E2, etc
    ai_expenses = {
        expense["expense_id"]: expense
        for expense in ai_result["expenses"]
    }

    #rule 1: Maximum amount allowed for one request
    max_request = policy["max_request_amount"]

    if total_requested > max_request:
        revision_needed = True
        issues.append(f"Total request exceeds the ${max_request:.2f} single-request limit.")
        add_check(checks, "FAIL", "Overall request exceeds the single-request limit.")
    else:
        add_check(checks, "PASS", "Overall request is within the single-request limit.")

    #rule 2: Club must have enough annual budget remaining
    if total_requested > remaining_budget:
        revision_needed = True
        shortfall = total_requested - remaining_budget

        issues.append(f"Request exceeds the club's remaining annual budget by ${shortfall:.2f}.")
        add_check(
            checks,
            "FAIL",
            f"Only ${remaining_budget:.2f} remains from the ${annual_budget:.2f} annual budget."
        )
    else:
        add_check(
            checks,
            "PASS",
            f"${remaining_budget:.2f} is available before this request."
        )

    #rule 3: Minimum submission lead time
    lead_days = calculate_lead_days(request["submission_date"], request["event_date"])

    minimum_days = policy["minimum_lead_days"]

    if lead_days < minimum_days:
        revision_needed = True
        issues.append(f"Request must be submitted at least {minimum_days} days before the event.")
        add_check(checks, "FAIL", f"Only {lead_days} day(s) of lead time.")
    else:
        add_check(checks, "PASS", f"{lead_days} day(s) of lead time.")

    #rule 4: Missing or unclear AI information needs human review
    if ai_result["missing_information"]:
        manual_review_needed = True
        issues.append("Missing information: "+ ", ".join(ai_result["missing_information"]))

    for expense in request["expenses"]:
        ai_expense = ai_expenses[expense["expense_id"]]

        if ai_expense["ambiguous"] or ai_expense["category"] == "unknown":
            manual_review_needed = True
            issues.append(f"{expense['expense_id']} could not be classified clearly.")

    #rule 5: Ineligible expense categories
    ineligible_categories = set(policy["ineligible_categories"])

    for expense in request["expenses"]:
        category = ai_expenses[expense["expense_id"]]["category"]

        if category in ineligible_categories:
            revision_needed = True
            eligible_amount -= expense["amount"]

            issues.append(f"{expense['expense_id']} ({category}) is not fundable.")

    #rule 6: Total food spending must stay under the per-person limit
    total_food = sum(
        expense["amount"]
        for expense in request["expenses"]
        if ai_expenses[expense["expense_id"]]["category"] == "food"
    )

    food_limit = (request["expected_participants"]* policy["food_per_person_limit"])

    if total_food > food_limit:
        revision_needed = True
        excess = total_food - food_limit
        eligible_amount -= excess

        issues.append(
            f"Food exceeds the allowed amount by ${excess:.2f}."
        )
        add_check(checks, "FAIL", f"Food limit is ${food_limit:.2f}.")
    elif total_food > 0:
        add_check(checks, "PASS", "Food spending is within the allowed limit.")

    #rule 7: Competition prize limit
    total_prizes = sum(
        expense["amount"]
        for expense in request["expenses"]
        if ai_expenses[expense["expense_id"]]["category"] == "prize"
    )

    prize_limit = policy["max_prize_amount"]

    if (
        ai_result["event_type"] == "competition"
        and total_prizes > prize_limit
    ):
        revision_needed = True
        excess = total_prizes - prize_limit
        eligible_amount -= excess

        issues.append(f"Competition prizes exceed the limit by ${excess:.2f}.")
        add_check(checks, "FAIL", f"Competition prize limit is ${prize_limit:.2f}.")
    elif total_prizes > 0:
        add_check(checks, "PASS", "No prize-limit problem detected.")

    #rule 8: Expensive reusable equipment requires a quote.
    quote_limit = policy["equipment_quote_threshold"]

    for expense in request["expenses"]:
        category = ai_expenses[expense["expense_id"]]["category"]

        if (
            category == "reusable_equipment"
            and expense["amount"] >= quote_limit
            and not expense["quote_available"]
        ):
            revision_needed = True
            issues.append(f"{expense['expense_id']} requires a supplier quote.")
            add_check(
                checks,
                "FAIL",
                f"Reusable equipment of ${quote_limit:.2f} or more needs a quote."
            )

    #the estimated eligible amount cannot exceed policy or annual budget limits.
    eligible_amount = min(eligible_amount, total_requested, max_request, remaining_budget)

    eligible_amount = round(max(0, eligible_amount), 2)

    if manual_review_needed:
        status = "MANUAL_REVIEW"
    elif revision_needed:
        status = "REVISION_REQUIRED"
    else:
        status = "READY_FOR_REVIEW"

    if status == "READY_FOR_REVIEW":
        budget_to_commit = eligible_amount
    else:
        budget_to_commit = 0.0

    remaining_after = round(max(0, remaining_budget - budget_to_commit), 2)

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

