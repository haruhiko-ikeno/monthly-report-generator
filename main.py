"""月次帳票 自動生成ツール

仕訳データ（CSV）から、月次決算で使用する帳票一式をExcelブックとして出力する。

使い方:
    python main.py --month 2026-01
    python main.py --month 2026-01 --config config.yaml
"""

import argparse
import sys
from pathlib import Path

from src import loader, reports
from src.excel_writer import write_workbook

BASE_DIR = Path(__file__).parent


def previous_month(month):
    y, m = (int(x) for x in month.split("-"))
    m -= 1
    if m == 0:
        y, m = y - 1, 12
    return f"{y:04d}-{m:02d}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="月次帳票を自動生成する")
    ap.add_argument("--month", required=True, help="対象年月（例: 2026-01）")
    ap.add_argument("--config", default="config.yaml", help="設定ファイル")
    args = ap.parse_args(argv)

    config = loader.load_config(BASE_DIR / args.config)

    print(f"[1/4] マスタを読み込みます")
    accounts, departments = loader.load_masters(BASE_DIR, config)

    print(f"[2/4] 仕訳データを読み込み、検証します")
    try:
        df = loader.load_journal(BASE_DIR, config, accounts, departments)
    except loader.ValidationError as e:
        print(f"  エラー: {e}", file=sys.stderr)
        return 1
    print(f"  明細 {len(df):,} 行  貸借一致 ✓  マスタ突合 ✓")

    month = args.month
    if month not in set(df["年月"]):
        print(f"  エラー: {month} の仕訳データがありません", file=sys.stderr)
        return 1

    months = loader.fiscal_months(config)
    prev_months = loader.previous_fiscal_months(config)
    prev_m = previous_month(month)
    threshold = config["variance_threshold"]

    print(f"[3/4] {month} の帳票を集計します")
    tb = reports.trial_balance(df, month)
    trend = reports.monthly_trend(df, months, section="PL")
    yoy = reports.year_on_year(df, months, prev_months, section="PL")
    dept_sales = reports.sales_by_department(df, months)
    dept_profit = reports.profit_by_department(df, months)
    variance = reports.variance_analysis(df, month, prev_m, threshold)

    company = config["company_name"]
    fy = config["fiscal_year"]
    sheets = [
        ("試算表", f"{company}　試算表　{month}", tb, (), None),
        ("月次推移表", f"{company}　月次推移表（損益）　{fy}年度", trend, (), None),
        ("前年度比較表", f"{company}　前年度比較表（損益）　{fy}年度 vs {fy - 1}年度",
         yoy, ("増減率",), None),
        ("部門別売上表", f"{company}　部門別売上表　{fy}年度", dept_sales, (),
         ("部門名", "合計")),
        ("部門別損益表", f"{company}　部門別損益表　{fy}年度", dept_profit, (), None),
        ("差異分析", f"{company}　差異分析　{prev_m} → {month}"
         f"（増減 {threshold:,}円以上）", variance, ("増減率",), None),
    ]

    out_dir = BASE_DIR / config["paths"]["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"月次帳票_{month.replace('-', '')}.xlsx"

    print(f"[4/4] Excelブックを出力します")
    write_workbook(out_path, company, month, sheets)

    print()
    print(f"完了: {out_path}")
    print(f"  試算表       : {len(tb)} 科目")
    print(f"  月次推移表   : {len(trend)} 科目 × 12ヶ月")
    print(f"  前年度比較表 : {len(yoy)} 科目")
    print(f"  部門別売上表 : {len(dept_sales) - 1} 部門")
    print(f"  部門別損益表 : {len(dept_profit) // 3} 部門")
    print(f"  差異分析     : {len(variance)} 科目が {threshold:,}円以上増減")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
