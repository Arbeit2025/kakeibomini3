from flask import Flask, request, redirect, url_for, flash, render_template_string
import os
import sqlite3
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kakeibo.db")

# ------------------------------
# DB
# ------------------------------
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = conn()
    cur = c.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            kind TEXT NOT NULL,
            category TEXT NOT NULL,
            amount INTEGER NOT NULL,
            memo TEXT,
            created_at TEXT NOT NULL
        )
    """)
    c.commit()
    c.close()

# ------------------------------
# Helpers
# ------------------------------
def month_range(yyyy_mm: str):
    y, m = yyyy_mm.split("-")
    y = int(y); m = int(m)
    start = date(y, m, 1)
    end = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return start.isoformat(), end.isoformat()

def yen(n: int) -> str:
    return f"{n:,}"

# ------------------------------
# HTML Template (内蔵)
# ------------------------------
HTML = """
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>単一ファイル家計簿</title>
<style>
body { background:#0f172a; color:#e2e8f0; font-family:sans-serif; margin:0; padding:20px; }
.card { background:#1e293b; padding:16px; border-radius:12px; margin-bottom:16px; }
input, select, textarea { width:100%; padding:8px; margin-top:4px; background:#0f172a; color:white; border:1px solid #334155; border-radius:6px; }
button { padding:8px 12px; border:0; border-radius:6px; cursor:pointer; }
.btn { background:#3b82f6; color:white; }
.danger { background:#ef4444; color:white; }
table { width:100%; border-collapse:collapse; margin-top:12px; }
th, td { border-bottom:1px solid #334155; padding:8px; text-align:left; }
.good { color:#22c55e; }
.bad { color:#ef4444; }
</style>
</head>
<body>

<h2>単一ファイル家計簿</h2>
<p>対象月: {{ month }} ({{ start }}〜{{ end }})</p>

<form method="get">
<input type="month" name="month" value="{{ month }}">
<button class="btn">切替</button>
</form>

{% with messages = get_flashed_messages() %}
  {% if messages %}
    {% for m in messages %}
      <p style="color:#facc15">{{ m }}</p>
    {% endfor %}
  {% endif %}
{% endwith %}

<div class="card">
<h3>入力</h3>
<form method="post" action="/add">
<label>日付</label>
<input type="date" name="entry_date" value="{{ today }}" required>

<label>種別</label>
<select name="kind">
<option value="expense">支出</option>
<option value="income">収入</option>
</select>

<label>カテゴリ</label>
<input name="category" required>

<label>金額</label>
<input type="number" name="amount" min="1" required>

<label>メモ</label>
<textarea name="memo"></textarea>

<br><br>
<button class="btn">記録</button>
</form>
</div>

<div class="card">
<h3>サマリー</h3>
<p>収入: <span class="good">¥{{ yen(income_sum) }}</span></p>
<p>支出: <span class="bad">¥{{ yen(expense_sum) }}</span></p>
<p>差額: 
<span class="{{ 'good' if balance>=0 else 'bad' }}">
¥{{ yen(balance) }}
</span>
</p>
</div>

<div class="card">
<h3>明細</h3>
<table>
<tr><th>日付</th><th>種別</th><th>カテゴリ</th><th>金額</th><th></th></tr>
{% for r in rows %}
<tr>
<td>{{ r["entry_date"] }}</td>
<td>{{ r["kind"] }}</td>
<td>{{ r["category"] }}</td>
<td class="{{ 'bad' if r['kind']=='expense' else 'good' }}">
¥{{ yen(r["amount"]) }}
</td>
<td>
<form method="post" action="/delete/{{ r['id'] }}">
<input type="hidden" name="month" value="{{ month }}">
<button class="danger">削除</button>
</form>
</td>
</tr>
{% endfor %}
</table>
</div>

</body>
</html>
"""

# ------------------------------
# Routes
# ------------------------------
@app.route("/")
def index():
    init_db()

    month = request.args.get("month") or datetime.now().strftime("%Y-%m")
    start, end = month_range(month)

    c = conn()
    cur = c.cursor()

    cur.execute("""
        SELECT * FROM entries
        WHERE entry_date >= ? AND entry_date < ?
        ORDER BY entry_date DESC
    """, (start, end))
    rows = cur.fetchall()

    cur.execute("""
        SELECT
        COALESCE(SUM(CASE WHEN kind='income' THEN amount END),0),
        COALESCE(SUM(CASE WHEN kind='expense' THEN amount END),0)
        FROM entries
        WHERE entry_date >= ? AND entry_date < ?
    """, (start, end))
    income_sum, expense_sum = cur.fetchone()

    c.close()

    balance = income_sum - expense_sum

    return render_template_string(
        HTML,
        month=month,
        start=start,
        end=end,
        today=date.today().isoformat(),
        rows=rows,
        income_sum=income_sum,
        expense_sum=expense_sum,
        balance=balance,
        yen=yen
    )

@app.route("/add", methods=["POST"])
def add():
    entry_date = request.form["entry_date"]
    kind = request.form["kind"]
    category = request.form["category"]
    memo = request.form.get("memo", "")

    try:
        amount = int(request.form["amount"])
    except:
        flash("金額エラー")
        return redirect(url_for("index"))

    c = conn()
    cur = c.cursor()
    cur.execute("""
        INSERT INTO entries (entry_date, kind, category, amount, memo, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (entry_date, kind, category, amount, memo, datetime.now().isoformat()))
    c.commit()
    c.close()

    return redirect(url_for("index", month=entry_date[:7]))

@app.route("/delete/<int:entry_id>", methods=["POST"])
def delete(entry_id):
    month = request.form.get("month")
    c = conn()
    cur = c.cursor()
    cur.execute("DELETE FROM entries WHERE id=?", (entry_id,))
    c.commit()
    c.close()
    return redirect(url_for("index", month=month))

if __name__ == "__main__":
    init_db()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")