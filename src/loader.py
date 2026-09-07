"""マスタ・仕訳データの読み込みと検証"""

from pathlib import Path

import pandas as pd
import yaml

REQUIRED_JOURNAL_COLUMNS = [
    "日付", "伝票番号", "部門コード", "勘定科目コード",
    "借方金額", "貸方金額", "摘要",
]


class ValidationError(Exception):
    """入力データが前提を満たさない場合に送出する"""


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_masters(base_dir, config):
    """勘定科目マスタ・部門マスタを読み込む"""
    accounts = pd.read_csv(
        Path(base_dir) / config["paths"]["accounts"], dtype={"勘定科目コード": str}
    )
    departments = pd.read_csv(Path(base_dir) / config["paths"]["departments"])
    return accounts, departments


def load_journal(base_dir, config, accounts, departments):
    """仕訳データを読み込み、マスタと突合したうえで検証する"""
    path = Path(base_dir) / config["paths"]["journal"]
    df = pd.read_csv(path, dtype={"勘定科目コード": str, "伝票番号": str})

    missing = [c for c in REQUIRED_JOURNAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"仕訳データに必要な列がありません: {missing}")

    df["日付"] = pd.to_datetime(df["日付"])
    df["年月"] = df["日付"].dt.strftime("%Y-%m")
    for col in ("借方金額", "貸方金額"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")

    # --- 検証1: 貸借一致 ---
    diff = int(df["借方金額"].sum() - df["貸方金額"].sum())
    if diff != 0:
        raise ValidationError(f"仕訳全体の貸借が一致しません（差額 {diff:,} 円）")

    # --- 検証2: 伝票単位の貸借一致 ---
    by_voucher = df.groupby("伝票番号")[["借方金額", "貸方金額"]].sum()
    unbalanced = by_voucher[by_voucher["借方金額"] != by_voucher["貸方金額"]]
    if not unbalanced.empty:
        raise ValidationError(
            f"貸借が一致しない伝票が {len(unbalanced)} 件あります: "
            f"{list(unbalanced.index[:5])}"
        )

    # --- 検証3: マスタ未登録コードの検出 ---
    unknown_acct = set(df["勘定科目コード"]) - set(accounts["勘定科目コード"])
    if unknown_acct:
        raise ValidationError(f"勘定科目マスタに存在しないコード: {sorted(unknown_acct)}")

    unknown_dept = set(df["部門コード"]) - set(departments["部門コード"])
    if unknown_dept:
        raise ValidationError(f"部門マスタに存在しないコード: {sorted(unknown_dept)}")

    # マスタ情報を結合
    df = df.merge(accounts, on="勘定科目コード", how="left")
    df = df.merge(departments, on="部門コード", how="left", suffixes=("", "_部門"))
    return df


def fiscal_months(config):
    """会計年度の12ヶ月を 'YYYY-MM' の昇順リストで返す"""
    year = config["fiscal_year"]
    start = config["fiscal_start_month"]
    months = []
    y, m = year, start
    for _ in range(12):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def previous_fiscal_months(config):
    """前会計年度の12ヶ月を返す"""
    prev = dict(config, fiscal_year=config["fiscal_year"] - 1)
    return fiscal_months(prev)
