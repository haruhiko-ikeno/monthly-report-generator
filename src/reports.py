"""月次帳票の集計ロジック

前職で毎月手作業により作成していた以下の帳票を、仕訳データから自動生成する。
  1. 試算表
  2. 月次推移表
  3. 前年度比較表
  4. 部門別売上表
  5. 差異分析表（前月比の増減が大きい科目の抽出）
"""

import pandas as pd

SALES_ACCOUNTS = ["401"]  # 売上高


def _signed_balance(sub):
    """貸借区分に応じた残高を返す（借方科目は借方－貸方、貸方科目はその逆）"""
    debit = sub["借方金額"].sum()
    credit = sub["貸方金額"].sum()
    return debit - credit if sub["貸借区分"].iloc[0] == "借方" else credit - debit


def trial_balance(df, month):
    """指定月の試算表を作成する（当月の発生高と期首からの累計残高）"""
    cur = df[df["年月"] == month]
    cum = df[df["年月"] <= month]

    rows = []
    for code, sub in cur.groupby("勘定科目コード"):
        cum_sub = cum[cum["勘定科目コード"] == code]
        rows.append({
            "勘定科目コード": code,
            "勘定科目名": sub["勘定科目名"].iloc[0],
            "区分": sub["区分"].iloc[0],
            "大分類": sub["大分類"].iloc[0],
            "当月借方": int(sub["借方金額"].sum()),
            "当月貸方": int(sub["貸方金額"].sum()),
            "当月残高": int(_signed_balance(sub)),
            "累計残高": int(_signed_balance(cum_sub)),
            "表示順": int(sub["表示順"].iloc[0]),
        })

    out = pd.DataFrame(rows).sort_values("表示順").drop(columns="表示順")
    return out.reset_index(drop=True)


def monthly_trend(df, months, section="PL"):
    """月次推移表を作成する（勘定科目 × 月）"""
    target = df[df["区分"] == section]

    records = []
    for code, sub in target.groupby("勘定科目コード"):
        row = {
            "勘定科目コード": code,
            "勘定科目名": sub["勘定科目名"].iloc[0],
            "大分類": sub["大分類"].iloc[0],
            "表示順": int(sub["表示順"].iloc[0]),
        }
        for m in months:
            row[m] = int(_signed_balance(sub[sub["年月"] == m])) if (sub["年月"] == m).any() else 0
        row["年度累計"] = sum(row[m] for m in months)
        records.append(row)

    out = pd.DataFrame(records).sort_values("表示順").drop(columns="表示順")
    return out.reset_index(drop=True)


def year_on_year(df, months, prev_months, section="PL"):
    """前年度比較表を作成する（当年度累計と前年度累計の対比）"""
    cur = monthly_trend(df, months, section)
    prev = monthly_trend(df, prev_months, section)

    cur_total = cur[["勘定科目コード", "勘定科目名", "大分類", "年度累計"]].rename(
        columns={"年度累計": "当年度"}
    )
    prev_total = prev[["勘定科目コード", "年度累計"]].rename(columns={"年度累計": "前年度"})

    out = cur_total.merge(prev_total, on="勘定科目コード", how="outer")
    out["当年度"] = out["当年度"].fillna(0).astype("int64")
    out["前年度"] = out["前年度"].fillna(0).astype("int64")
    out["増減額"] = out["当年度"] - out["前年度"]
    out["増減率"] = out.apply(
        lambda r: (r["増減額"] / r["前年度"]) if r["前年度"] != 0 else None, axis=1
    )
    return out.reset_index(drop=True)


def sales_by_department(df, months):
    """部門別売上表を作成する（部門 × 月）"""
    sales = df[df["勘定科目コード"].isin(SALES_ACCOUNTS)]

    records = []
    for dept, sub in sales.groupby("部門コード"):
        row = {"部門コード": dept, "部門名": sub["部門名"].iloc[0]}
        for m in months:
            s = sub[sub["年月"] == m]
            row[m] = int(s["貸方金額"].sum() - s["借方金額"].sum())
        row["年度累計"] = sum(row[m] for m in months)
        records.append(row)

    out = pd.DataFrame(records).sort_values("部門コード").reset_index(drop=True)

    total = {"部門コード": "", "部門名": "合計"}
    for m in months:
        total[m] = int(out[m].sum())
    total["年度累計"] = int(out["年度累計"].sum())
    return pd.concat([out, pd.DataFrame([total])], ignore_index=True)


def variance_analysis(df, month, prev_month, threshold):
    """差異分析表を作成する

    前月比でしきい値以上増減した損益科目を抽出し、
    増減額の大きい順に並べる。各科目について、当月の主要な仕訳
    （金額上位3件）を摘要付きで添え、変動要因の特定に使えるようにする。
    """
    pl = df[df["区分"] == "PL"]
    cur = pl[pl["年月"] == month]
    prev = pl[pl["年月"] == prev_month]

    rows = []
    for code in sorted(set(cur["勘定科目コード"]) | set(prev["勘定科目コード"])):
        c = cur[cur["勘定科目コード"] == code]
        p = prev[prev["勘定科目コード"] == code]
        c_amt = int(_signed_balance(c)) if not c.empty else 0
        p_amt = int(_signed_balance(p)) if not p.empty else 0
        diff = c_amt - p_amt
        if abs(diff) < threshold:
            continue

        name = c["勘定科目名"].iloc[0] if not c.empty else p["勘定科目名"].iloc[0]

        # 当月の主要仕訳（金額上位3件）を摘要付きで抽出
        detail = c.assign(金額=c["借方金額"] + c["貸方金額"]).nlargest(3, "金額")
        notes = " / ".join(
            f"{r['部門名']}：{r['摘要']} {int(r['金額']):,}円"
            for _, r in detail.iterrows()
        )

        rows.append({
            "勘定科目コード": code,
            "勘定科目名": name,
            "前月": p_amt,
            "当月": c_amt,
            "増減額": diff,
            "増減率": (diff / p_amt) if p_amt != 0 else None,
            "当月の主要仕訳（上位3件）": notes,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.reindex(out["増減額"].abs().sort_values(ascending=False).index).reset_index(drop=True)


def profit_by_department(df, months):
    """部門別損益表を作成する（部門 × 月、売上・費用・利益）

    ★TODO が3か所あります。埋めてから実行してください。
    """
    records = []

    for dept, sub in df.groupby("部門コード"):
        name = sub["部門名"].iloc[0]

        # ------------------------------------------------------------------
        # TODO① この部門の「収益」の行だけを取り出す
        #   ヒント: 大分類 列が "収益" の行に絞る
        #           sales_by_department() の絞り込みの書き方を参照
        # ------------------------------------------------------------------
        revenue = None

        # ------------------------------------------------------------------
        # TODO② この部門の「費用」の行だけを取り出す
        # ------------------------------------------------------------------
        expense = None

        if revenue is None or expense is None:
            raise NotImplementedError("TODO① と TODO② を埋めてください")

        r_row = {"部門コード": dept, "部門名": name, "区分": "売上"}
        e_row = {"部門コード": dept, "部門名": name, "区分": "費用"}
        p_row = {"部門コード": dept, "部門名": name, "区分": "利益"}

        for m in months:
            # --------------------------------------------------------------
            # TODO③ その月の売上と費用を求める
            #   ヒント: 月で絞る       revenue[revenue["年月"] == m]
            #           金額を求める   _signed_balance(絞り込んだ表)
            #           _signed_balance は貸借区分を見て計算を切り替えるので、
            #           収益にも費用にもそのまま使える
            #   注意:   その月にデータが無いと空の表になるので、
            #           空のときは 0 にする必要がある
            # --------------------------------------------------------------
            r = 0
            e = 0

            r_row[m] = int(r)
            e_row[m] = int(e)
            p_row[m] = int(r) - int(e)

        for row in (r_row, e_row, p_row):
            row["年度累計"] = sum(row[m] for m in months)
            records.append(row)

    out = pd.DataFrame(records)
    return out.sort_values("部門コード", kind="stable").reset_index(drop=True)
