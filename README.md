# ClubFund – Phase 2 (INF1103 Team 7)

AI-assisted pre-screening of student club funding requests. Phase 2 refactors the Phase 1
program into classes, adds an admin **funding policy editor** (new feature) and a
**web GUI** (advanced feature). The command-line menu still works as before.

## Project structure

Each manager is a folder with **one class per file**. The manager's main file (e.g. `ai_manager/ai_manager.py`)
holds the manager class and imports every other class in its folder, and the folder's `__init__.py` re-exports
them, so code elsewhere still writes `from ai_manager import AIManager`.

```
main.py                     Launcher: `python main.py` (CLI) or `python main.py --gui` (web GUI)
command_line_app.py         CommandLineApp: the student/admin terminal menus
clubfund_app.py             ClubFundApp: runs the pipeline (budget -> AI -> rules -> save)
io_manager/                 IO Manager
    io_manager.py           ConsoleIO (all terminal input/output)
ai_manager/                 AI Manager
    ai_manager.py           AIManager  (main file, imports the classes below)
    ai_classifier.py        AIClassifier (interface)
    openai_classifier.py    OpenAIClassifier
    fallback_classifier.py  FallbackClassifier
    prompt_builder.py       PromptBuilder
    response_validator.py   ResponseValidator
    ai_service_error.py     AIServiceError
    ai_config.py            model name, retries, timeout, AI instructions
logic_manager/              Logic Manager
    logic_manager.py        LogicManager (main file, imports every rule)
    rule_context.py         RuleContext
    business_rule.py        BusinessRule (abstract)
    category_limit_rule.py  CategoryLimitRule (abstract)
    request_limit_rule.py, remaining_budget_rule.py, lead_time_rule.py, unclear_information_rule.py,
    equipment_quote_rule.py, ineligible_category_rule.py, food_limit_rule.py, prize_limit_rule.py
data_manager/               Data Manager
    data_manager.py         DataManager (main file, imports the classes below)
    repository.py           Repository (interface)
    json_request_repository.py, json_policy_repository.py, json_budget_repository.py
    budget_ledger.py        BudgetLedger
    excel_report_exporter.py ExcelReportExporter
    data_config.py          location of the data/ folder
gui_manager/                Web GUI (advanced feature)
    gui_manager.py          WebGUI (main file, imports the form classes)
    request_form.py         RequestForm
    policy_form.py          PolicyForm
    gui_config.py           page settings, templates folder
models/                     Shared domain classes used by every manager
    models.py               gathers all classes and constants below
    funding_request.py, expense.py, policy.py, policy_error.py, assessment.py, check.py, funding_record.py
    constants.py            valid categories / event types, rule names, type aliases
templates/                  HTML pages for the GUI
data/                       requests.json, policy.json, club_budgets.json, test_cases.json
test_clubfund.py            Automated test suite (unittest)
test_script.py              Interactive offline runner for data/test_cases.json (from Phase 1)
```

## Environment variables

| Variable | Needed for | Default |
|---|---|---|
| `OPENAI_API_KEY` | Live AI classification. Without it, requests fall back to `MANUAL_REVIEW` | – |
| `OPENAI_MODEL` | Model name | `gpt-5.6-luna` |
| `CLUBFUND_HOST` / `CLUBFUND_PORT` | GUI address | `127.0.0.1` / `5000` (`0.0.0.0` in Docker) |
| `CLUBFUND_SECRET_KEY` | GUI session key | random per run |
| `CLUBFUND_ADMIN_PASSWORD` | Admin log-in (GUI and CLI) | `1234` |

Never commit API keys. Pass them with `-e` or a local `.env` file (ignored by Git).

## Run with Docker (recommended)

```bash
docker build -t clubfund .

# Command-line menu
docker run -it --rm -e OPENAI_API_KEY=<your key> clubfund

# Web GUI – then open http://localhost:5000
docker run -it --rm -p 5000:5000 -e OPENAI_API_KEY=<your key> clubfund python main.py --gui

# Keep saved requests/policy changes between runs (mount the data folder)
docker run -it --rm -p 5000:5000 -v "$(pwd)/data:/app/data" -e OPENAI_API_KEY=<your key> clubfund python main.py --gui
```

## Run tests

```bash
docker run --rm clubfund python -m unittest -v        # automated suite, no API key needed
docker run -it --rm clubfund python test_script.py    # interactive offline test menu
```

Without Docker: `pip install -r req.txt`, then `python main.py`, `python main.py --gui`
or `python -m unittest -v`.

## Continuous Integration

`.github/workflows/ci.yml` runs on every push and pull request:
1. **unit-tests** – installs `req.txt` on Python 3.11 and runs `python -m unittest -v`.
2. **docker** – builds the image and runs the same tests inside the container.

## Roles

* **Student:** chooses their club when logging in (GUI and CLI). Students submit funding requests for
  that club only, and only see their own club's budget and requests.
* **Admin:** sees every club's requests, club budgets, the summary and Excel export, and the funding
  policy. Admins cannot create funding requests.
* **Admin password:** `1234` by default (GUI and CLI). Set `CLUBFUND_ADMIN_PASSWORD` to change it, e.g.
  `docker run ... -e CLUBFUND_ADMIN_PASSWORD=newpass clubfund`. The CLI allows 3 tries.

## Using the new features

* **Funding policy editor (admin):** GUI → log in as *Admin* → *Funding Policy*, or CLI admin menu option
  **5**. Admins change limits and turn individual rules on or off (the *Unclear AI information* rule is
  always on). Values are validated, saved to `data/policy.json` and used for new requests; a turned-off
  rule shows as `SKIPPED` in the result. Saved assessments are not recalculated.
* **Web GUI:** all Phase 1 functions in the browser, with the same Student/Admin roles.

## Code style

All functions and methods have type hints; `mypy` reports no issues
(`mypy --ignore-missing-imports --check-untyped-defs --exclude '^test_' .`; the test file deliberately passes invalid values).
