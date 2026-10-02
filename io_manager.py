from datetime import date

def show_menu():
    #Display the main command-line menu.
    print("\n=== CLUBFUND ===")
    print("1. New funding request")
    print("2. View all requests")
    print("3. View club annual budget")
    print("4. View summary")
    print("5. Export Excel report")
    print("6. Exit")

def get_choice():
    #Get a valid menu choice from 1 to 6.
    while True:
        choice = input("Choose 1-6: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= 6:
            return int(choice)

        print("Invalid choice. Enter a number from 1 to 6.")


def get_text(prompt):
    #Get text that cannot be empty.
    while True:
        value = input(prompt).strip()
        if value:
            return value

        print("Input cannot be empty.")

def get_positive_int(prompt):
    #Get a whole number greater than 0
    while True:
        value = input(prompt).strip()

        if value.isdigit() and int(value) > 0:
            return int(value)

        print("Enter a whole number greater than 0.")

def get_money(prompt):
    #Get a money value of 0 or more
    while True:
        try:
            value = float(input(prompt).strip())

            if value >= 0:
                return round(value, 2)

        except ValueError:
            pass

        print("Enter a valid amount, e.g. 250 or 250.50.")

def get_yes_no(prompt):
    #Return True for yes and False for no.
    while True:
        answer = input(f"{prompt} (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True

        if answer in ("n", "no"):
            return False

        print("Enter y or n.")

def get_date(prompt):
    #Get a valid date in YYYY-MM-DD format.
    while True:
        value = input(f"{prompt} (YYYY-MM-DD): ").strip()

        try:
            date.fromisoformat(value)
            return value

        except ValueError:
            print("Invalid date. Example: 2026-10-15.")

# ============================================================
# NEW: Clubs are selected from club_budgets.json instead of typed freely.
# This prevents spelling variations from creating duplicate club names.
# ============================================================
def select_club(club_names):
    #Let the user choose from clubs that have an annual budget.
    print("\nAvailable clubs:")

    for number, club in enumerate(club_names, start=1):
        print(f"{number}. {club}")

    while True:
        choice = input("Select club: ").strip()

        if choice.isdigit():
            choice = int(choice)

            if 1 <= choice <= len(club_names):
                return club_names[choice - 1]

        print("Invalid club selection.")

# ============================================================
# CHANGED: collect_request() now receives club_names.
# REMOVED: user-entered remaining_budget.
# The remaining annual budget is calculated by data_manager.py.
# ============================================================
def collect_request(request_id, club_names):
    #Collect one complete funding request.
    #The user no longer enters a remaining budget.
    #The Data Manager calculates it from previous saved requests.
    print("\n--- New Funding Request ---")

    request = {
        "request_id": request_id,
        "club_name": select_club(club_names),
        "event_title": get_text("Event title: "),
        "event_description": get_text("Describe the event: "),
        "event_date": get_date("Event date"),
        "submission_date": get_date("Submission date"),
        "expected_participants": get_positive_int("Expected participants: "),
        "expenses": []
    }

    number_of_expenses = get_positive_int("Number of expense items: ")

    for number in range(1, number_of_expenses + 1):
        print(f"\nExpense {number}")

        request["expenses"].append({
            "expense_id": f"E{number}",
            "description": get_text("Description: "),
            "amount": get_money("Amount ($): "),
            "quote_available": get_yes_no("Supplier quote available?")
        })

    return request


def show_result(record):
    #Display the final funding assessment.
    assessment = record.get("assessment")

    if not assessment:
        print("\nThis request has no completed assessment.")
        return

    print("\n=== FUNDING ASSESSMENT ===")
    print(f"Request ID: {record['request_id']}")
    print(f"Club: {record['club_name']}")
    print(f"Event: {record['event_title']}")

    print("\nCurrent request:")
    print(f"Requested: ${assessment['total_requested']:.2f}")
    print(f"Estimated eligible: ${assessment['estimated_eligible_amount']:.2f}")
    print(f"Status: {assessment['status']}")

    print("\nChecks:")
    for check in assessment["checks"]:
        print(f"- {check['result']}: {check['message']}")

    if assessment["issues"]:
        print("\nIssues:")
        for issue in assessment["issues"]:
            print(f"- {issue}")

    print("\nThis is a pre-screening result, not final funding approval.")


def show_requests(records, title="Requests"):
    #Display a short list of saved requests.
    print(f"\n=== {title} ===")

    if not records:
        print("No requests found.")
        return

    for record in records:
        assessment = record.get("assessment") or {}
        status = assessment.get(
            "status",
            record.get("processing_status", "UNKNOWN")
        )
        total = assessment.get("total_requested", 0)

        print(
            f"{record['request_id']} | "
            f"{record['club_name']} | "
            f"${total:.2f} | "
            f"{status}"
        )


def show_summary(summary):
    #Display summary statistics.
    print("\n=== SUMMARY ===")
    print(f"Total requests: {summary['total_requests']}")
    print(f"Ready for review: {summary['ready_for_review']}")
    print(f"Revision required: {summary['revision_required']}")
    print(f"Manual review: {summary['manual_review']}")
    print(f"AI failed: {summary['ai_failed']}")
    print(f"Total requested: ${summary['total_requested']:.2f}")
    print(f"Estimated eligible: ${summary['estimated_eligible']:.2f}")