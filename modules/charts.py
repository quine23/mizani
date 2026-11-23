"""Graphical reports drawn with matplotlib and returned as PNG bytes.

Figure() is used directly (not pyplot) so charts are safe to draw while the web
server handles several requests at once.
"""
import io

from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

INCOME_COLOR = "#1B7F54"
EXPENSE_COLOR = "#B8432F"
INK = "#172B2E"
MUTED = "#5B7074"
GRID = "#D5DDD8"


def _thousands(value, _position):
    return f"{value:,.0f}"


def _finish(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor="white")
    return buffer.getvalue()


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)


def monthly_chart_png(series, year):
    """Grouped bars: income and expenses for each month of the year."""
    fig = Figure(figsize=(8, 3.6), dpi=110)
    ax = fig.subplots()
    positions = list(range(len(series)))
    width = 0.38
    ax.bar([p - width / 2 for p in positions], [s["income"] for s in series],
           width, label="Income", color=INCOME_COLOR)
    ax.bar([p + width / 2 for p in positions], [s["expenses"] for s in series],
           width, label="Expenses", color=EXPENSE_COLOR)
    ax.set_xticks(positions)
    ax.set_xticklabels([s["label"] for s in series])
    ax.yaxis.set_major_formatter(FuncFormatter(_thousands))
    ax.set_ylabel("KES", color=MUTED, fontsize=9)
    ax.set_title(f"Income and expenses by month, {year}", color=INK, fontsize=11, loc="left")
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    _style(ax)
    fig.tight_layout()
    return _finish(fig)


def category_chart_png(rows, title):
    """Horizontal bars of spending per category, largest at the top."""
    height = max(2.2, 0.5 * len(rows) + 1.2)
    fig = Figure(figsize=(8, height), dpi=110)
    ax = fig.subplots()
    if not rows:
        ax.text(0.5, 0.5, "No expenses recorded for this month", ha="center", va="center",
                color=MUTED, fontsize=11, transform=ax.transAxes)
        ax.set_axis_off()
    else:
        names = [r["name"] for r in rows][::-1]
        totals = [r["total"] for r in rows][::-1]
        bars = ax.barh(names, totals, color=EXPENSE_COLOR, height=0.6)
        top = max(totals)
        for bar, value in zip(bars, totals):
            ax.text(value + top * 0.01, bar.get_y() + bar.get_height() / 2,
                    f"{value:,.0f}", va="center", fontsize=9, color=INK)
        ax.set_xlim(0, top * 1.15)
        ax.xaxis.set_major_formatter(FuncFormatter(_thousands))
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        _style(ax)
    ax.set_title(title, color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    return _finish(fig)
