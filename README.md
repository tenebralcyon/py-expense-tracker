\# py-expense-tracker



py-expense-tracker is a beginner-friendly but powerful command-line expense tracker written in Python. It stores expenses in a local SQLite database and provides tools to add and manage transactions, import bank-style CSV files, automatically categorize expenses using keyword rules, track totals by category, set monthly budgets, compare spending against budgets, and export monthly data back to CSV for reporting.



This project was built to be simple enough to run from Windows Command Prompt, while still showcasing advanced real-world features like rule-based auto-categorization and budget vs spending summaries.



──────────────────────────────────────────────────────────────────────────────



FEATURES



1\) Local database storage (SQLite)

\- Saves all data into a local file-based database (expenses.db)

\- Keeps expense history persistent between runs



2\) Add expenses manually

\- Add transactions with date, amount, category, and optional note

\- Supports “today” as a valid date input



3\) List expenses with filters

\- View a formatted list of transactions

\- Filter by:

&nbsp; - category

&nbsp; - month (YYYY-MM)

&nbsp; - date range (--from / --to)

&nbsp; - keyword search in descriptions/notes

&nbsp; - limit number of results shown



4\) Totals and category breakdown

\- Shows overall spending total

\- Shows breakdown by category

\- Supports monthly totals using --month YYYY-MM



5\) Monthly budgets (advanced feature)

\- Set per-category budgets for a given month

\- Display budgets for that month

\- Monthly totals can compare spending vs budgets and show remaining amount and OK/OVER status



6\) Auto-categorization rules (advanced feature)

\- Create keyword-based rules such as “starbucks → food”

\- Rules use priority (higher priority wins)

\- Categorization is case-insensitive substring matching

\- If no rule matches, category becomes “uncategorized”



7\) Import from CSV (advanced feature)

\- Import expenses from a CSV file (bank-style export)

\- Dry-run mode by default for safety (preview without inserting)

\- Use --commit to insert into the database

\- Automatically applies category rules to each imported row

\- Supports negative amounts (refunds)



8\) Export to CSV

\- Export a single month of data into a CSV file

\- Useful for Excel/Google Sheets or future accounting workflows



──────────────────────────────────────────────────────────────────────────────



EXAMPLE WORKFLOW 



Step 1: Add auto-categorization rules

py expense.py rule-add --keyword starbucks --category food --priority 10

py expense.py rule-add --keyword amazon --category shopping --priority 5

py expense.py rule-add --keyword uber --category transport --priority 5

py expense.py rule-add --keyword rent --category rent --priority 100

py expense.py rule-add --keyword hydro --category utilities --priority 20

py expense.py rule-add --keyword "whole foods" --category groceries --priority 8



View rules:

py expense.py rule-list



Step 2: Import expenses from a CSV file

Dry-run preview (safe test):

py expense.py import examples\\sample\_bank.csv



Commit import into the database:

py expense.py import examples\\sample\_bank.csv --commit



Step 3: List expenses

py expense.py list --limit 50



Filter examples:

py expense.py list --category food --limit 20

py expense.py list --month 2026-01 --limit 50

py expense.py list --search refund --limit 20

py expense.py list --from 2026-01-01 --to 2026-01-15 --limit 50



Step 4: Totals

All time totals:

py expense.py totals



Monthly totals:

py expense.py totals --month 2026-01



Step 5: Set budgets for a month (budget vs spending feature)

py expense.py budget-set --month 2026-01 --category food --amount 200

py expense.py budget-set --month 2026-01 --category groceries --amount 400

py expense.py budget-set --month 2026-01 --category transport --amount 150

py expense.py budget-set --month 2026-01 --category rent --amount 1800

py expense.py budget-set --month 2026-01 --category utilities --amount 250

py expense.py budget-set --month 2026-01 --category shopping --amount 300



Show budgets:

py expense.py budget-show --month 2026-01



Run totals again (this is where the “advanced” budget comparison happens):

py expense.py totals --month 2026-01



Step 6: Delete an expense by ID

py expense.py delete 3



Step 7: Export monthly data to CSV

py expense.py export --month 2026-01 --out exports\\export\_2026-01.csv



──────────────────────────────────────────────────────────────────────────────



PROJECT FILES



examples/

\- Contains sample input data (for import testing)

\- Example file: examples/sample\_bank.csv



outputs/

\- Contains captured sample outputs from real test runs

\- Useful for showcasing the program’s capabilities on GitHub

\- Example file: outputs/FULL\_DEMO\_OUTPUT.txt



exports/

\- Contains exported CSV results (usually ignored by git unless you choose otherwise)



──────────────────────────────────────────────────────────────────────────────



NOTES



\- Refunds should be represented as negative amounts (example: -15.00)

\- Auto-categorization depends on keyword rules and priorities





