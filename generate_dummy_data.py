"""
ダミー仕訳データ生成スクリプト

実務の仕訳日記帳と同じ形式（1行＝1つの借方または貸方明細）で、
2会計年度分（前年度・当年度）の仕訳データを生成する。

月次帳票生成ツールの動作確認用。実データは一切含まない。
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20260907
random.seed(SEED)

OUT = Path(__file__).parent / "data" / "journal.csv"

DEPTS = ["D01", "D02", "D03", "D04"]

# 部門ごとの月間売上の基準額（円）
DEPT_SALES_BASE = {
    "D01": 18_000_000,   # ホテル事業部
    "D02": 6_500_000,    # レンタカー事業部
    "D03": 9_000_000,    # 駐車場事業部
    "D04": 0,            # 管理部門（売上なし）
}

# 月別の季節指数（4月始まり）。繁忙期は夏と年末年始。
SEASONALITY = {
    1: 0.92, 2: 0.88, 3: 1.02, 4: 0.98, 5: 1.05, 6: 0.95,
    7: 1.22, 8: 1.35, 9: 1.04, 10: 1.00, 11: 0.96, 12: 1.18,
}

# 費用科目と、月間の基準額・変動幅
EXPENSES = [
    ("501", "仕入高",       0.28, 0.06),   # 売上比例（比率, ばらつき）
    ("601", "給料手当",     None, None),
    ("602", "法定福利費",   None, None),
    ("603", "旅費交通費",   None, None),
    ("604", "通信費",       None, None),
    ("605", "水道光熱費",   None, None),
    ("606", "地代家賃",     None, None),
    ("607", "支払手数料",   0.035, 0.005),  # 売上比例（決済手数料）
    ("609", "保険料",       None, None),
    ("610", "消耗品費",     None, None),
    ("611", "広告宣伝費",   None, None),
    ("612", "修繕費",       None, None),
    ("613", "雑費",         None, None),
]

# 固定的な費用の月額レンジ（円）
FIXED_EXPENSE_RANGE = {
    "601": (9_000_000, 10_500_000),
    "602": (1_300_000, 1_550_000),
    "603": (280_000, 520_000),
    "604": (180_000, 240_000),
    "605": (900_000, 1_600_000),
    "606": (4_200_000, 4_200_000),   # 家賃は定額
    "609": (150_000, 150_000),       # 保険料は定額（年払を月割）
    "610": (200_000, 450_000),
    "611": (300_000, 1_200_000),
    "612": (0, 900_000),
    "613": (50_000, 180_000),
}

# 減価償却費（毎月定額で計上する決算整理仕訳）
DEPRECIATION = {"D01": 620_000, "D02": 410_000, "D03": 350_000, "D04": 95_000}

# 意図的に仕込む異常値（差異分析シートで検出されることを確認するため）
# (年, 月, 部門, 科目コード, 追加金額, 摘要)
ANOMALIES = [
    (2025, 8, "D01", "612", 3_800_000, "客室空調設備の緊急修繕"),
    (2025, 11, "D02", "611", 2_400_000, "年末キャンペーン広告出稿"),
    (2026, 1, "D03", "605", 1_500_000, "寒波による電気使用量増加"),
]


def month_range(start_year, start_month, months):
    y, m = start_year, start_month
    for _ in range(months):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def random_day(y, m):
    if m == 12:
        last = 31
    else:
        last = (date(y, m + 1, 1) - timedelta(days=1)).day
    return date(y, m, random.randint(1, last))


def jitter(base, pct):
    return int(base * random.uniform(1 - pct, 1 + pct))


def main():
    rows = []
    voucher = 0

    def add(d, dept, acct, debit, credit, memo, tax=""):
        nonlocal voucher
        rows.append({
            "日付": d.isoformat(),
            "伝票番号": f"{voucher:06d}",
            "部門コード": dept,
            "勘定科目コード": acct,
            "借方金額": debit,
            "貸方金額": credit,
            "摘要": memo,
            "税区分": tax,
        })

    # 前年度(2024/4)から当年度(2026/3)まで 24ヶ月
    for y, m in month_range(2024, 4, 24):

        # ---- 売上計上 ----
        for dept in DEPTS:
            base = DEPT_SALES_BASE[dept]
            if base == 0:
                continue
            # 前年度から当年度にかけて緩やかに成長させる
            growth = 1.0 if y <= 2025 or (y == 2025 and m < 4) else 1.06
            total = int(base * SEASONALITY[m] * growth * random.uniform(0.95, 1.05))

            # 1ヶ月あたり複数本に分けて計上
            n = random.randint(8, 14)
            amounts = [total // n] * n
            amounts[-1] += total - sum(amounts)
            for amt in amounts:
                voucher += 1
                d = random_day(y, m)
                add(d, dept, "103", amt, 0, "売上計上（掛）", "課税売上10%")
                add(d, dept, "401", 0, amt, "売上計上（掛）", "課税売上10%")

        month_sales = sum(
            r["貸方金額"] for r in rows
            if r["勘定科目コード"] == "401" and r["日付"].startswith(f"{y:04d}-{m:02d}")
        )

        # ---- 費用計上 ----
        for code, name, ratio, spread in EXPENSES:
            for dept in DEPTS:
                if ratio is not None:
                    # 売上比例費用は売上のある部門のみ
                    if DEPT_SALES_BASE[dept] == 0:
                        continue
                    dept_sales = sum(
                        r["貸方金額"] for r in rows
                        if r["勘定科目コード"] == "401"
                        and r["部門コード"] == dept
                        and r["日付"].startswith(f"{y:04d}-{m:02d}")
                    )
                    amt = jitter(dept_sales * ratio, spread)
                else:
                    lo, hi = FIXED_EXPENSE_RANGE[code]
                    share = 0.4 if dept == "D01" else (0.2 if dept != "D04" else 0.2)
                    amt = int(random.randint(lo, hi) * share) if hi > 0 else 0

                if amt <= 0:
                    continue

                voucher += 1
                d = random_day(y, m)
                credit_acct = "201" if code == "501" else "202"
                add(d, dept, code, amt, 0, f"{name} 計上", "課税仕入10%")
                add(d, dept, credit_acct, 0, amt, f"{name} 計上", "課税仕入10%")

        # ---- 異常値の上乗せ ----
        for ay, am, adept, acode, aamt, amemo in ANOMALIES:
            if (y, m) == (ay, am):
                voucher += 1
                d = random_day(y, m)
                add(d, adept, acode, aamt, 0, amemo, "課税仕入10%")
                add(d, adept, "202", 0, aamt, amemo, "課税仕入10%")

        # ---- 決算整理仕訳：減価償却費の月次計上 ----
        for dept, amt in DEPRECIATION.items():
            voucher += 1
            d = date(y, m, 28) if m != 2 else date(y, m, 28)
            add(d, dept, "608", amt, 0, "減価償却費 月次計上（決算整理）")
            add(d, dept, "152", 0, amt, "減価償却費 月次計上（決算整理）")

        # ---- 決算整理仕訳：前払費用の振替（保険料の月割） ----
        voucher += 1
        d = date(y, m, 28)
        add(d, "D04", "609", 150_000, 0, "前払費用より保険料へ振替（決算整理）")
        add(d, "D04", "107", 0, 150_000, "前払費用より保険料へ振替（決算整理）")

        # ---- 決算整理仕訳：未払費用の計上（水道光熱費の見越） ----
        voucher += 1
        d = date(y, m, 28)
        accrual = random.randint(180_000, 420_000)
        add(d, "D01", "605", accrual, 0, "水道光熱費の見越計上（決算整理）")
        add(d, "D01", "203", 0, accrual, "水道光熱費の見越計上（決算整理）")

        # ---- 入金・支払 ----
        voucher += 1
        d = date(y, m, 25)
        collect = int(month_sales * random.uniform(0.85, 0.95))
        add(d, "D04", "102", collect, 0, "売掛金回収")
        add(d, "D04", "103", 0, collect, "売掛金回収")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["日付", "伝票番号", "部門コード", "勘定科目コード",
                        "借方金額", "貸方金額", "摘要", "税区分"],
        )
        w.writeheader()
        w.writerows(rows)

    debit = sum(r["借方金額"] for r in rows)
    credit = sum(r["貸方金額"] for r in rows)
    print(f"生成完了: {OUT}")
    print(f"  明細件数 : {len(rows):,} 行")
    print(f"  借方合計 : {debit:,} 円")
    print(f"  貸方合計 : {credit:,} 円")
    print(f"  貸借差額 : {debit - credit:,} 円  {'✓ 一致' if debit == credit else '✗ 不一致'}")


if __name__ == "__main__":
    main()
