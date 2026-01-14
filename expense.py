from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List, Tuple


DB_NAME = "expenses.db"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spent_on TEXT NOT NULL,          -- YYYY-MM-DD
            amount_cents INTEGER NOT NULL,   -- store money as cents (avoids float issues)
            category TEXT NOT NULL,
            note TEXT
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_spent_on ON expenses(spent_on);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS budgets (
            month TEXT NOT NULL,             -- YYYY-MM
            category TEXT NOT NULL,
            amount_cents INTEGER NOT NULL,
            PRIMARY KEY (month, category)
        );
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,           -- substring match (case-insensitive)
            category TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rules_priority ON rules(priority DESC);")

    conn.commit()


def parse_date(s: str) -> str:
    """Return YYYY-MM-DD string. Accepts YYYY-MM-DD or 'today'."""
    s = s.strip().lower()
    if s == "today":
        return date.today().isoformat()
    try:
        dt = datetime.strptime(s, "%Y-%m-%d").date()
        return dt.isoformat()
    except ValueError:
        raise SystemExit("Invalid date. Use YYYY-MM-DD or 'today'.")


def dollars_to_cents(s: str) -> int:
    """
    Convert a string like '12.34' or '12' to cents (int).
    """
    s = s.strip()
    if not s:
        raise SystemExit("Amount cannot be empty.")
    # basic validation
    if s.count(".") > 1:
        raise SystemExit("Invalid amount format.")
    parts = s.split(".")
    if len(parts) == 1:
        dollars = parts[0]
        cents = "0"
    else:
        dollars, cents = parts
    if not dollars.isdigit() or (cents and not cents.isdigit()):
        raise SystemExit("Amount must be a number like 12 or 12.34")

    if len(cents) == 0:
        cents = "0"
    if len(cents) == 1:
        cents = cents + "0"
    if len(cents) > 2:
        # round down extra precision
        cents = cents[:2]

    return int(dollars) * 100 + int(cents)


def cents_to_dollars(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"

def parse_date_ymd(s: str) -> date:
    """Parse YYYY-MM-DD into a date object."""
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit("Invalid date. Use YYYY-MM-DD.")


def parse_month_ym(s: str) -> str:
    """Validate YYYY-MM and return it."""
    s = s.strip()
    if len(s) != 7 or s[4] != "-":
        raise SystemExit("Month must be YYYY-MM.")
    y, m = s.split("-", 1)
    if not (y.isdigit() and m.isdigit()):
        raise SystemExit("Month must be YYYY-MM.")
    mm = int(m)
    if mm < 1 or mm > 12:
        raise SystemExit("Month must be YYYY-MM.")
    return s


def month_of(spent_on_yyyy_mm_dd: str) -> str:
    return spent_on_yyyy_mm_dd[:7]


def normalize_category(s: str) -> str:
    return s.strip().lower()



def add_expense(conn: sqlite3.Connection, spent_on: str, amount_cents: int, category: str, note: Optional[str]) -> None:
    category = normalize_category(category)
    if not category:
        raise SystemExit("Category cannot be empty.")
    note = (note or "").strip() or None

    conn.execute(
        "INSERT INTO expenses (spent_on, amount_cents, category, note) VALUES (?, ?, ?, ?)",
        (spent_on, amount_cents, category, note),
    )
    conn.commit()


def list_expenses(
    conn: sqlite3.Connection,
    limit: int = 20,
    category: Optional[str] = None,
    month: Optional[str] = None,      # YYYY-MM
    date_from: Optional[str] = None,  # YYYY-MM-DD
    date_to: Optional[str] = None,    # YYYY-MM-DD
    search: Optional[str] = None,     # substring match in note
) -> List[Tuple[int, str, int, str, Optional[str]]]:
    sql = "SELECT id, spent_on, amount_cents, category, note FROM expenses"
    params = []
    where = []

    if category:
        where.append("category = ?")
        params.append(normalize_category(category))

    if month:
        month = parse_month_ym(month)
        where.append("substr(spent_on, 1, 7) = ?")
        params.append(month)

    if date_from:
        date_from = parse_date(date_from)
        where.append("spent_on >= ?")
        params.append(date_from)

    if date_to:
        date_to = parse_date(date_to)
        where.append("spent_on <= ?")
        params.append(date_to)

    if search:
        where.append("COALESCE(note,'') LIKE ?")
        params.append(f"%{search}%")

    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += " ORDER BY spent_on DESC, id DESC LIMIT ?"
    params.append(limit)

    cur = conn.execute(sql, params)
    return cur.fetchall()


def totals(
    conn: sqlite3.Connection,
    month: Optional[str] = None,  # YYYY-MM
) -> Tuple[int, List[Tuple[str, int]], List[Tuple[str, int]]]:
    """
    Returns:
      total_cents,
      totals_by_category,
      budgets_by_category (for that month; empty if month not provided)
    """
    params = []
    where = ""
    if month:
        month = parse_month_ym(month)
        where = "WHERE substr(spent_on, 1, 7) = ?"
        params.append(month)

    total_cents = conn.execute(f"SELECT COALESCE(SUM(amount_cents), 0) FROM expenses {where}", params).fetchone()[0]

    by_cat = conn.execute(
        f"""
        SELECT category, COALESCE(SUM(amount_cents), 0) AS total
        FROM expenses
        {where}
        GROUP BY category
        ORDER BY total DESC;
        """,
        params,
    ).fetchall()

    budgets = []
    if month:
        budgets = conn.execute(
            """
            SELECT category, amount_cents
            FROM budgets
            WHERE month = ?
            ORDER BY amount_cents DESC;
            """,
            (month,),
        ).fetchall()

    return int(total_cents), [(c, int(t)) for c, t in by_cat], [(c, int(b)) for c, b in budgets]



def delete_expense(conn: sqlite3.Connection, expense_id: int) -> None:
    cur = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    if cur.rowcount == 0:
        raise SystemExit(f"No expense found with id {expense_id}.")

def set_budget(conn: sqlite3.Connection, month: str, category: str, amount_cents: int) -> None:
    month = parse_month_ym(month)
    category = normalize_category(category)
    conn.execute(
        """
        INSERT INTO budgets (month, category, amount_cents)
        VALUES (?, ?, ?)
        ON CONFLICT(month, category) DO UPDATE SET amount_cents = excluded.amount_cents
        """,
        (month, category, amount_cents),
    )
    conn.commit()


def list_budgets(conn: sqlite3.Connection, month: str) -> List[Tuple[str, int]]:
    month = parse_month_ym(month)
    return [(c, int(a)) for c, a in conn.execute(
        "SELECT category, amount_cents FROM budgets WHERE month = ? ORDER BY amount_cents DESC",
        (month,),
    ).fetchall()]


def add_rule(conn: sqlite3.Connection, keyword: str, category: str, priority: int) -> None:
    keyword = keyword.strip().lower()
    if not keyword:
        raise SystemExit("Keyword cannot be empty.")
    category = normalize_category(category)
    conn.execute(
        "INSERT INTO rules (keyword, category, priority) VALUES (?, ?, ?)",
        (keyword, category, priority),
    )
    conn.commit()


def list_rules(conn: sqlite3.Connection) -> List[Tuple[int, str, str, int]]:
    return conn.execute(
        "SELECT id, keyword, category, priority FROM rules ORDER BY priority DESC, id ASC"
    ).fetchall()


def categorize_with_rules(conn: sqlite3.Connection, text: str) -> str:
    """
    Simple rule engine: if keyword is contained in description/note (case-insensitive),
    pick the highest priority match. If none, return 'uncategorized'.
    """
    t = (text or "").lower()
    for _, kw, cat, _prio in conn.execute(
        "SELECT id, keyword, category, priority FROM rules ORDER BY priority DESC, id ASC"
    ):
        if kw in t:
            return cat
    return "uncategorized"


def import_csv(
    conn: sqlite3.Connection,
    csv_path: Path,
    date_col: str = "date",
    amount_col: str = "amount",
    desc_col: str = "description",
    date_format: str = "%Y-%m-%d",
    dry_run: bool = True,
) -> int:
    """
    Imports rows from a bank-like CSV containing date/amount/description columns.
    - Auto-categorizes based on rules table.
    - Writes note=description, category=rule match.
    - dry_run=True prints/returns count but does not insert.
    """
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    to_insert = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SystemExit("CSV has no headers.")

        for row in reader:
            raw_date = (row.get(date_col) or "").strip()
            raw_amt = (row.get(amount_col) or "").strip()
            raw_desc = (row.get(desc_col) or "").strip()

            if not raw_date or not raw_amt:
                continue

            try:
                d = datetime.strptime(raw_date, date_format).date().isoformat()
            except ValueError:
                raise SystemExit(f"Date parse failed for '{raw_date}'. Check --date-format.")

            # Allow amounts like -12.34 or 12.34
            amt = raw_amt.replace(",", "").strip()
            sign = -1 if amt.startswith("-") else 1
            amt_num = amt[1:] if amt.startswith("-") else amt
            amount_cents = dollars_to_cents(amt_num) * sign

            category = categorize_with_rules(conn, raw_desc)
            note = raw_desc or None

            to_insert.append((d, amount_cents, category, note))

    if dry_run:
        return len(to_insert)

    conn.executemany(
        "INSERT INTO expenses (spent_on, amount_cents, category, note) VALUES (?, ?, ?, ?)",
        to_insert,
    )
    conn.commit()
    return len(to_insert)


def export_month_csv(conn: sqlite3.Connection, month: str, out_path: Path) -> None:
    month = parse_month_ym(month)
    rows = conn.execute(
        """
        SELECT spent_on, amount_cents, category, COALESCE(note,'')
        FROM expenses
        WHERE substr(spent_on, 1, 7) = ?
        ORDER BY spent_on ASC, id ASC
        """,
        (month,),
    ).fetchall()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "amount", "category", "note"])
        for spent_on, amount_cents, category, note in rows:
            w.writerow([spent_on, cents_to_dollars(int(amount_cents)), category, note])


def main() -> None:
    parser = argparse.ArgumentParser(description="Expense Tracker (SQLite) - add, list, totals, delete.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize the database")

    p_add = sub.add_parser("add", help="Add an expense")
    p_add.add_argument("--date", required=True, help="YYYY-MM-DD or 'today'")
    p_add.add_argument("--amount", required=True, help="Amount in dollars, e.g., 12.34")
    p_add.add_argument("--category", required=True, help="Category, e.g., food, rent")
    p_add.add_argument("--note", default="", help="Optional note")

    p_list = sub.add_parser("list", help="List recent expenses")
    p_list.add_argument("--limit", type=int, default=20, help="Max rows to show (default: 20)")
    p_list.add_argument("--category", default="", help="Filter by category (exact match)")
    p_list.add_argument("--month", default="", help="Filter by month YYYY-MM")
    p_list.add_argument("--from", dest="date_from", default="", help="Start date YYYY-MM-DD")
    p_list.add_argument("--to", dest="date_to", default="", help="End date YYYY-MM-DD")
    p_list.add_argument("--search", default="", help="Substring search in note")

    p_tot = sub.add_parser("totals", help="Show totals (overall + by category)")
    p_tot.add_argument("--month", default="", help="Filter by month YYYY-MM")

    p_del = sub.add_parser("delete", help="Delete an expense by id")
    p_del.add_argument("id", type=int, help="Expense id to delete")

    p_budget = sub.add_parser("budget-set", help="Set monthly budget for a category")
    p_budget.add_argument("--month", required=True, help="YYYY-MM")
    p_budget.add_argument("--category", required=True, help="Category name")
    p_budget.add_argument("--amount", required=True, help="Budget amount in dollars, e.g., 300 or 300.00")

    p_budget_show = sub.add_parser("budget-show", help="Show budgets for a month")
    p_budget_show.add_argument("--month", required=True, help="YYYY-MM")

    p_rule_add = sub.add_parser("rule-add", help="Add an auto-categorization rule")
    p_rule_add.add_argument("--keyword", required=True, help="Substring keyword (case-insensitive)")
    p_rule_add.add_argument("--category", required=True, help="Category to assign")
    p_rule_add.add_argument("--priority", type=int, default=0, help="Higher priority wins")

    p_rule_list = sub.add_parser("rule-list", help="List categorization rules")

    p_import = sub.add_parser("import", help="Import bank CSV (dry-run by default)")
    p_import.add_argument("csv_path", help="Path to CSV file")
    p_import.add_argument("--date-col", default="date", help="CSV column name for date")
    p_import.add_argument("--amount-col", default="amount", help="CSV column name for amount")
    p_import.add_argument("--desc-col", default="description", help="CSV column name for description")
    p_import.add_argument("--date-format", default="%Y-%m-%d", help="Python strptime format for date")
    p_import.add_argument("--commit", action="store_true", help="Actually insert into database (otherwise dry-run)")

    p_export = sub.add_parser("export", help="Export a month of expenses to CSV")
    p_export.add_argument("--month", required=True, help="YYYY-MM")
    p_export.add_argument("--out", default="exports/month.csv", help="Output path for CSV")


    args = parser.parse_args()

    db_path = Path(__file__).parent / DB_NAME
    conn = connect(db_path)

    # Ensure schema exists for all commands (init is still available explicitly)
    init_db(conn)

    if args.cmd == "init":
        print(f"Database ready: {db_path}")
        return

    if args.cmd == "add":
        spent_on = parse_date(args.date)
        amount_cents = dollars_to_cents(args.amount)
        add_expense(conn, spent_on, amount_cents, args.category, args.note)
        print(f"Added: {spent_on}  ${cents_to_dollars(amount_cents)}  [{args.category}] {args.note}".rstrip())
        return

    if args.cmd == "list":
        rows = list_expenses(
            conn,
            limit=args.limit,
            category=args.category.strip() or None,
            month=args.month.strip() or None,
            date_from=args.date_from.strip() or None,
            date_to=args.date_to.strip() or None,
            search=args.search.strip() or None,
        )

        if not rows:
            print("No expenses found.")
            return

        print("ID  Date        Amount    Category    Note")
        print("--  ----------  --------  ----------  ----")
        for rid, spent_on, amount_cents, cat, note in rows:
            amt = cents_to_dollars(amount_cents)
            note = note or ""
            print(f"{rid:<3} {spent_on:<10}  {amt:>8}  {cat:<10}  {note}")
        return
        
    if args.cmd == "totals":
        month = args.month.strip() or None
        total_cents, by_cat, budgets = totals(conn, month=month)
        label = f" for {month}" if month else ""
        print(f"Total{label}: ${cents_to_dollars(total_cents)}")

        spent_map = {cat: cents for cat, cents in by_cat}
        budget_map = {cat: cents for cat, cents in budgets}

        if by_cat:
            print("\nBy category:")
            for cat, cents in by_cat:
                line = f"  {cat:<12} ${cents_to_dollars(cents)}"
                if month and cat in budget_map:
                    remaining = budget_map[cat] - cents
                    status = "OK" if remaining >= 0 else "OVER"
                    line += f"   (budget ${cents_to_dollars(budget_map[cat])}, remaining ${cents_to_dollars(remaining)} -> {status})"
                print(line)

        if month and budgets:
            # show categories that have budgets but no spending yet
            missing = [c for c in budget_map.keys() if c not in spent_map]
            if missing:
                print("\nBudgeted categories with no spending:")
                for c in missing:
                    print(f"  {c:<12} budget ${cents_to_dollars(budget_map[c])}")

        return

    if args.cmd == "delete":
        delete_expense(conn, args.id)
        print(f"Deleted expense id {args.id}.")
        return

    if args.cmd == "budget-set":
        month = args.month
        category = args.category
        amount_cents = dollars_to_cents(args.amount)
        set_budget(conn, month, category, amount_cents)
        print(f"Budget set: {parse_month_ym(month)} [{normalize_category(category)}] = ${cents_to_dollars(amount_cents)}")
        return

    if args.cmd == "budget-show":
        month = parse_month_ym(args.month)
        rows = list_budgets(conn, month)
        if not rows:
            print(f"No budgets set for {month}.")
            return
        print(f"Budgets for {month}:")
        for cat, cents in rows:
            print(f"  {cat:<12} ${cents_to_dollars(cents)}")
        return

    if args.cmd == "rule-add":
        add_rule(conn, args.keyword, args.category, args.priority)
        print(f"Rule added: '{args.keyword.lower()}' -> [{normalize_category(args.category)}] priority={args.priority}")
        return

    if args.cmd == "rule-list":
        rows = list_rules(conn)
        if not rows:
            print("No rules yet.")
            return
        print("Rules (higher priority wins):")
        for rid, kw, cat, pr in rows:
            print(f"  {rid:<3} priority={pr:<3}  '{kw}' -> {cat}")
        return

    if args.cmd == "import":
        p = Path(args.csv_path).expanduser().resolve()
        count = import_csv(
            conn,
            p,
            date_col=args.date_col,
            amount_col=args.amount_col,
            desc_col=args.desc_col,
            date_format=args.date_format,
            dry_run=(not args.commit),
        )
        if args.commit:
            print(f"Imported {count} rows into database.")
        else:
            print(f"[DRY-RUN] Would import {count} rows. Re-run with --commit to insert.")
        return

    if args.cmd == "export":
        month = parse_month_ym(args.month)
        out = Path(args.out).expanduser().resolve()
        export_month_csv(conn, month, out)
        print(f"Exported {month} to: {out}")
        return


if __name__ == "__main__":
    main()
