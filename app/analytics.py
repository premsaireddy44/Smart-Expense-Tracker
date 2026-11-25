"""Spending analytics with pandas.

Everything here is a plain function: give it a table of transactions (a DataFrame)
and today's date, get back a dictionary. No database, no web - so it is easy to test.

Columns the table must have:
    date, amount, type ("income"/"expense"), category (a name), description,
    category_source, suggested_category_id
"""
import calendar
from datetime import date

import pandas as pd

from app.suggestions import memory_key

FY_START_MONTH = {"uk": 4, "india": 4}      # both start on 6 Apr (UK) / 1 Apr (India)
FY_START_DAY = {"uk": 6, "india": 1}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
RECENT_DAYS = 90


def money(value) -> float:
    return round(float(value), 2)


def percent_change(new, old):
    """+20.0 means 'up 20%'. None when there is nothing to compare with."""
    if not old:
        return None
    return round((new - old) / old * 100, 1)


def month_label(period) -> str:
    return str(period)                       # "2026-10"


def last_12_months(df, today):
    """Income, spending and savings for each of the last 12 months (empty months show 0)."""
    this_month = pd.Period(today, "M")
    months = pd.period_range(this_month - 11, this_month, freq="M")
    if df.empty:
        totals = pd.DataFrame(0.0, index=months, columns=["income", "expense"])
    else:
        df = df.assign(month=df["date"].dt.to_period("M"))
        totals = df.pivot_table(index="month", columns="type", values="amount", aggfunc="sum", fill_value=0)
        totals = totals.reindex(months, fill_value=0)
        for column in ("income", "expense"):
            if column not in totals:
                totals[column] = 0.0
    return [
        {
            "month": month_label(m),
            "income": money(row["income"]),
            "expense": money(row["expense"]),
            "savings": money(row["income"] - row["expense"]),
        }
        for m, row in totals.iterrows()
    ]


def category_changes(expenses, today):
    """Spending per category this month compared with last month, biggest first."""
    this_month = pd.Period(today, "M")
    if expenses.empty:
        return []
    months = expenses["date"].dt.to_period("M")
    now = expenses[months == this_month].groupby("category")["amount"].sum()
    before = expenses[months == this_month - 1].groupby("category")["amount"].sum()
    table = pd.concat([now.rename("now"), before.rename("before")], axis=1).fillna(0)
    table = table.sort_values("now", ascending=False)
    return [
        {
            "category": name,
            "this_month": money(row["now"]),
            "last_month": money(row["before"]),
            "change_percent": percent_change(row["now"], row["before"]),
        }
        for name, row in table.iterrows()
    ]


def top_merchants(expenses, today):
    """Where the money went in the last 90 days: similar descriptions are grouped together."""
    cutoff = pd.Timestamp(today) - pd.Timedelta(days=RECENT_DAYS)
    recent = expenses[expenses["date"] > cutoff]
    if recent.empty:
        return []
    recent = recent.assign(name=recent["description"].map(memory_key))
    recent = recent[recent["name"] != ""]
    grouped = recent.groupby("name")["amount"].agg(total="sum", count="count")
    grouped = grouped.sort_values("total", ascending=False).head(5)
    return [{"name": n.title(), "total": money(r["total"]), "count": int(r["count"])} for n, r in grouped.iterrows()]


def weekday_pattern(expenses, today):
    """Total spending on each weekday over the last 90 days."""
    cutoff = pd.Timestamp(today) - pd.Timedelta(days=RECENT_DAYS)
    recent = expenses[expenses["date"] > cutoff]
    totals = recent.groupby(recent["date"].dt.dayofweek)["amount"].sum() if not recent.empty else {}
    return [{"day": WEEKDAYS[i], "total": money(totals[i]) if i in totals else 0.0} for i in range(7)]


def unusual_spending(expenses, today):
    """Expenses much bigger than normal for their category (mean + 2 standard deviations).

    A category needs at least 5 expenses first, otherwise 'normal' is just a guess.
    Only the last 30 days are reported so the list stays fresh.
    """
    found = []
    cutoff = pd.Timestamp(today) - pd.Timedelta(days=30)
    for name, group in expenses.groupby("category"):
        if len(group) < 5:
            continue
        limit = group["amount"].mean() + 2 * group["amount"].std()
        for _, row in group[(group["amount"] > limit) & (group["date"] > cutoff)].iterrows():
            found.append({
                "description": row["description"],
                "category": name,
                "amount": money(row["amount"]),
                "usual_limit": money(limit),
                "date": row["date"].date().isoformat(),
            })
    return sorted(found, key=lambda x: x["date"], reverse=True)[:5]


def financial_year(df, today, fy="uk"):
    """Totals since the start of the current financial year (UK: 6 April, India: 1 April)."""
    start = date(today.year, FY_START_MONTH[fy], FY_START_DAY[fy])
    if today < start:
        start = date(today.year - 1, FY_START_MONTH[fy], FY_START_DAY[fy])
    inside = df[df["date"] >= pd.Timestamp(start)] if not df.empty else df
    income = inside.loc[inside["type"] == "income", "amount"].sum() if not inside.empty else 0
    expense = inside.loc[inside["type"] == "expense", "amount"].sum() if not inside.empty else 0
    return {
        "label": f"{start.year}/{str(start.year + 1)[2:]}",
        "start": start.isoformat(),
        "income": money(income),
        "expense": money(expense),
        "savings": money(income - expense),
    }


def month_end_estimate(expenses, today):
    """If spending continues at this month's pace, what will the month total be?"""
    this_month = pd.Period(today, "M")
    spent = expenses.loc[expenses["date"].dt.to_period("M") == this_month, "amount"].sum() if not expenses.empty else 0
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    return {
        "spent_so_far": money(spent),
        "estimate": money(spent / today.day * days_in_month),
        "days_left": days_in_month - today.day,
    }


def suggestion_accuracy(df):
    """How often the user kept our suggestion. Only counts rows where we made a suggestion
    and the user then made a choice (kept it = 'accepted', changed it = 'user')."""
    if df.empty:
        return {"checked": 0, "kept": 0, "percent": None}
    judged = df[df["suggested_category_id"].notna() & df["category_source"].isin(["accepted", "user"])]
    kept = int((judged["category_source"] == "accepted").sum())
    checked = int(len(judged))
    return {"checked": checked, "kept": kept, "percent": round(kept / checked * 100) if checked else None}


def write_insights(months, changes, estimate, unusual, merchants):
    """Plain-English sentences built from the numbers above."""
    notes = []
    now = months[-1]
    before = months[-2] if len(months) > 1 else None

    if now["income"] > 0:
        rate = round(now["savings"] / now["income"] * 100)
        notes.append(f"You are saving {rate}% of your income this month." if rate >= 0
                     else f"You have spent {-rate}% more than you earned this month.")
    if before and before["expense"] > 0 and now["expense"] > 0:
        change = percent_change(now["expense"], before["expense"])
        if change is not None and abs(change) >= 10:
            direction = "more" if change > 0 else "less"
            notes.append(f"You spent {abs(change):.0f}% {direction} than last month so far.")
    big = [c for c in changes if c["change_percent"] is not None and c["change_percent"] >= 30 and c["this_month"] >= 500]
    if big:
        c = max(big, key=lambda x: x["change_percent"])
        notes.append(f"{c['category']} is up {c['change_percent']:.0f}% on last month.")
    if estimate["spent_so_far"] > 0 and estimate["days_left"] > 0:
        notes.append(f"At this pace you will spend about {estimate['estimate']:,.0f} by the end of the month.")
    if unusual:
        u = unusual[0]
        notes.append(f"'{u['description']}' ({u['amount']:,.0f}) is much bigger than your usual {u['category']} spending.")
    if merchants:
        notes.append(f"Your biggest spending lately: {merchants[0]['name']} ({merchants[0]['total']:,.0f}).")
    if not notes:
        notes.append("Add a few more transactions and your insights will appear here.")
    return notes


def build_analytics(df, today, fy="uk"):
    """The one function the route calls."""
    if df.empty:
        df = pd.DataFrame(columns=["date", "amount", "type", "category", "description",
                                   "category_source", "suggested_category_id"])
        df["date"] = pd.to_datetime(df["date"])
        df["amount"] = df["amount"].astype(float)
    expenses = df[df["type"] == "expense"]

    months = last_12_months(df, today)
    changes = category_changes(expenses, today)
    merchants = top_merchants(expenses, today)
    estimate = month_end_estimate(expenses, today)
    unusual = unusual_spending(expenses, today)
    return {
        "months": months,
        "category_changes": changes,
        "top_merchants": merchants,
        "weekdays": weekday_pattern(expenses, today),
        "unusual": unusual,
        "financial_year": financial_year(df, today, fy),
        "month_end": estimate,
        "suggestion_accuracy": suggestion_accuracy(df),
        "insights": write_insights(months, changes, estimate, unusual, merchants),
    }