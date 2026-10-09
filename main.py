import io_manager
import ai_manager
import logic_manager
import data_manager


def process_new_request(records, policy, budgets, club_names):
    """
    1. Collect the request info from user.
    2. Check which annual budget applies.
    3. Calculate remaining club budget.
    4. Send the request to ai_manager.
    5. Apply business rules.
    6. Save & display the processed records.
    """
    # Generate the next ID, such as CF0001 or CF0002.
    request_id = data_manager.next_request_id(records)
    request = io_manager.collect_request(request_id, club_names)

    # Use the event year as the funding year.
    request["funding_year"] = int(request["event_date"][:4])
    # Calculate the club's annual budget from saved history.
    budget_info = data_manager.get_budget_info(records,budgets,request["club_name"],request["funding_year"])
    # Every request still attempts to pass through AI API. If API fails, ai_manager returns fallback so all AI-dependent classifications are marked unknown/ambiguous.
    ai_result, ai_error = ai_manager.analyse_request(request)
    # The request passes through logic_manager even when AI fails.
    assessment = logic_manager.assess_request(request,ai_result,policy,budget_info)

    if ai_error:
        processing_status = "AI_FAILED"
    else:
        processing_status = "PROCESSED"

    processed_record = data_manager.make_record(request,ai_result,assessment,processing_status,ai_error)
    saved, save_error = data_manager.add_request(records,processed_record)

    if not saved:
        io_manager.show_message(save_error)
        return

    if ai_error:
        io_manager.show_message("\nAI service was unavailable. ")

    io_manager.show_result(processed_record)


def main():
    # Load records from previous program runs.
    records, request_error = data_manager.load_requests()
    # Load funding rules.
    policy, policy_error = data_manager.load_policy()
    # Load each club's fixed annual budget.
    budgets, budget_error = data_manager.load_club_budgets()
    if request_error:
        io_manager.show_message(request_error)

    if policy_error:
        io_manager.show_message(policy_error)
        return

    if budget_error:
        io_manager.show_message(budget_error)
        return

    club_names = data_manager.get_club_names(budgets)
    while True:
        role = io_manager.get_user_role()
        io_manager.show_menu(role)
        choice = io_manager.get_choice(role)

        # 1. New funding request
        if choice == 1:
            process_new_request(records,policy,budgets,club_names)

        # 2. View all requests
        elif choice == 2:
            io_manager.show_requests(records,"All Requests")

        # 3. View club annual budget
        elif choice == 3:
            club_name = io_manager.choose_budget_club(club_names)
            year = io_manager.get_year()

            budget_info = data_manager.get_budget_info(records,budgets,club_name,year)

            io_manager.show_budget(budget_info,club_name,year)

        # 4. View summary
        elif choice == 4:
            summary = data_manager.build_summary(records)
            io_manager.show_summary(summary)

        # 5. Export Excel report
        elif choice == 5:
            message = data_manager.export_to_excel(records,budgets)
            io_manager.show_message(message)

        # 6. Exit
        elif choice == 6:
            io_manager.show_message("Goodbye.")
            break

if __name__ == "__main__":
    main()