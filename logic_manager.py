from datetime import date

#add all expense amounts
def calculate_total(expenses):
    return round(sum(expense["amount"] for expense in expenses), 2)

