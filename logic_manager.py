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
