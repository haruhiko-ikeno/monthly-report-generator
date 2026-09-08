# 用語集

このリポジトリで使っている名前の対応表です。

会計の実務担当者がコードを読むとき、また開発者が会計側の用語を確認するときの
両方向の橋渡しを目的としています。

---

## 1. 会計用語

コード内の名前は、会計英語をそのまま使っています。

| 英語 | 読み | 日本語 | 使用箇所 |
|---|---|---|---|
| account | アカウント | 勘定科目 | `data/accounts.csv`（勘定科目マスタ） |
| journal | ジャーナル | 仕訳帳 | `data/journal.csv`（仕訳データ） |
| ledger | レジャー | 総勘定元帳 | ※参考（本ツールでは未使用） |
| debit / credit | デビット／クレジット | 借方／貸方 | `借方金額` / `貸方金額` |
| balance | バランス | 残高 | `_signed_balance()` |
| trial balance | トライアル バランス | 試算表 | `trial_balance()` |
| variance analysis | バリアンス アナリシス | 差異分析 | `variance_analysis()` |
| year on year (YoY) | イヤー オン イヤー | 前年同期比 | `year_on_year()` |
| fiscal year | フィスカル イヤー | 会計年度 | `fiscal_months()` |
| department | ディパートメント | 部門 | `data/departments.csv` |
| master | マスター | マスタ | `load_masters()` |
| reconciliation | レコンシリエーション | 突合・照合 | マスタ突合の検証 |

### 貸借区分について

勘定科目マスタが持つ `貸借区分` は、残高計算の方向を決めます。

| 大分類 | 貸借区分 | 残高の計算 |
|---|---|---|
| 資産・費用 | 借方 | 借方 − 貸方 |
| 負債・純資産・収益 | 貸方 | 貸方 − 借方 |

この区別をせずに一律で「借方 − 貸方」とすると、売上高や負債が
マイナス表示になります。`_signed_balance()` はこの切り替えを行う関数です。

---

## 2. ファイル・ディレクトリ

| 名前 | 由来 | 役割 |
|---|---|---|
| `main.py` | main | エントリポイント（実行の入口） |
| `src/` | source | ソースコードを置くディレクトリ |
| `loader.py` | load + -er | 読み込みと検証 |
| `reports.py` | report | 集計ロジック |
| `excel_writer.py` | write + -er | Excel出力・書式設定 |
| `config.yaml` | configuration | 設定ファイル |
| `requirements.txt` | requirement | 依存ライブラリの一覧 |
| `generate_dummy_data.py` | generate + dummy | 動作確認用データの生成 |
| `__init__.py` | initialize | ディレクトリをパッケージとして扱う目印 |
| `.gitignore` | ignore | Gitの管理対象外にするファイルの指定 |
| `.csv` | Comma-Separated Values | カンマ区切りのテキスト形式 |

`-er` は「〜するもの」を表します（`loader` = 読み込むもの、`writer` = 書き出すもの）。

---

## 3. コード内の略語

| 略語 | 元の語 | 意味 |
|---|---|---|
| `df` | DataFrame | 表形式データ（pandas の慣習） |
| `cur` | current | 当月・当年度 |
| `prev` | previous | 前月・前年度 |
| `cum` | cumulative | 累計 |
| `sub` | subset | 抽出した一部 |
| `amt` | amount | 金額 |
| `diff` | difference | 差額 |
| `col` | column | 列 |
| `fmt` | format | 書式 |
| `pct` | percent | 率 |
| `wb` / `ws` | workbook / worksheet | Excelのブック／シート |
| `args` | arguments | コマンドライン引数 |
| `out` | output | 出力 |
| `tb` | trial balance | 試算表 |
| `yoy` | year on year | 前年度比較 |
| `dept` | department | 部門 |

その他:

- **threshold** … しきい値。`variance_threshold` は差異分析の抽出基準（円）
- **validation** … 検証。`ValidationError` は入力データが前提を満たさない場合に送出
- **mapping** … 対応づけ。`column_mapping` はCSVの列名と内部名の対応表

---

## 4. 設計上の用語

### パイプライン (pipeline／パイプライン)

複数の処理を順に繋ぎ、前の工程の出力を次の工程の入力とする構成のこと。
本ツールは次の4工程で構成しています。

```
読み込み  →  検証  →  集計  →  出力
loader.py    loader.py   reports.py   excel_writer.py
```

工程を分けているため、入力形式が変わっても `loader.py` だけを差し替えれば済み、
集計ロジックには影響しません。月次決算の実務（証憑回収 → 計上 → 照合 → 資料作成）も
同じ構造をしています。

### マスタ突合（マスタとつごう）

仕訳データに現れるコードが、マスタに登録済みかを照合すること。
`load_journal()` では、勘定科目コードと部門コードの両方について確認し、
未登録のコードがあれば処理を中止します。

マスタに無いコードを含んだまま集計すると、その仕訳が
どの科目・部門にも属さないまま黙って欠落するため、
集計前に検出する必要があります。

---

## 5. 使用ライブラリ

| 名前 | 読み | 由来 | 用途 |
|---|---|---|---|
| pandas | パンダス | panel data | 表形式データの集計 |
| openpyxl | オープンパイエックスエル | open + py + xl | Excelファイルの生成 |
| PyYAML | パイヤムル | Python + YAML | 設定ファイルの読み込み |
| argparse | アーグパース | argument parser | コマンドライン引数の解釈 |

ファイル形式の読み方: `.csv` シーエスブイ / `.yaml` ヤムル / `.json` ジェイソン / `.md` エムディー

---

## 6. 命名の方針

関数名は「動詞 + 対象」または「対象 + 条件」の形に統一しています。

```
load_journal          仕訳を読み込む
write_workbook        ブックを書き出す
sales_by_department   売上を部門別に
generate_dummy_data   ダミーデータを生成する
```

先頭にアンダースコアが付く名前（`_signed_balance`, `_write_sheet`）は、
そのモジュール内部でのみ使用する関数であることを示す慣習です。
