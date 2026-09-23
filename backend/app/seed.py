import json
from app.db import connect
from app.engines.amortization import equal_payment_schedule

def repair_legacy_settle_rows(conn):
    """修复旧版本把"续还剩余利息/结清余额"对调落库的历史对照行（幂等）。

    旧行特征：remaining_interest 错存为结清额，故等于 remaining_principal，
    而 settle_amount 错存为利息合计、与之不等；新行恒有 settle_amount ==
    remaining_principal。命中则交换两项并把超额利息符号翻正。
    """
    rows = conn.execute(
        "SELECT id, result_json FROM calc_runs WHERE kind='settle_compare'").fetchall()
    fixed = 0
    for row in rows:
        try:
            data = json.loads(row["result_json"])
        except (TypeError, ValueError):
            continue
        rp, ri, sa = data.get("remaining_principal"), data.get("remaining_interest"), data.get("settle_amount")
        ex = data.get("extra_interest")
        if not all(isinstance(x, (int, float)) for x in (rp, ri, sa)):
            continue
        # 新行恒有 settle_amount == remaining_principal 且超额利息非负；
        # 旧行结清额错存为利息合计（通常不等本金），超额利息为负
        is_legacy = ri == rp and (sa != rp or (isinstance(ex, (int, float)) and ex < 0))
        if is_legacy:
            data["remaining_interest"], data["settle_amount"] = sa, ri
            if isinstance(data.get("extra_interest"), (int, float)):
                data["extra_interest"] = -data["extra_interest"]
            conn.execute("UPDATE calc_runs SET result_json=? WHERE id=?",
                (json.dumps(data, ensure_ascii=False), row["id"]))
            fixed += 1
    if fixed:
        conn.commit()
    return fixed

def init_db():
    conn = connect()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS loans(id INTEGER PRIMARY KEY, name TEXT, principal REAL, annual_rate REAL, months INTEGER);
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS calc_runs(id INTEGER PRIMARY KEY, kind TEXT, loan_id INTEGER, input_json TEXT, result_json TEXT, created_at TEXT);
    """)
    repair_legacy_settle_rows(conn)
    if conn.execute("SELECT COUNT(*) c FROM loans").fetchone()["c"] == 0:
        conn.execute("INSERT INTO loans(name,principal,annual_rate,months) VALUES ('首套样例',1000000,3.5,360)")
        conn.execute("INSERT INTO loans(name,principal,annual_rate,months) VALUES ('高利率种子',800000,6.8,240)")
        conn.execute("INSERT INTO settings(key,value) VALUES ('method','equal_payment')")
        sch = equal_payment_schedule(1000000, 3.5, 360)
        slim = {"monthly_payment": sch["monthly_payment"], "total_interest": sch["total_interest"], "preview": sch["rows"][:3]}
        conn.execute("INSERT INTO calc_runs(kind,loan_id,input_json,result_json,created_at) VALUES ('schedule',1,?,?,datetime('now'))",
            (json.dumps({"principal": 1000000, "annual_rate": 3.5, "months": 360}), json.dumps(slim)))
        conn.commit()
    conn.close()
