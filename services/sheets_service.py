"""
Googleスプレッドシート連携およびローカルCSVフォールバック管理モジュール

- シート1: inventory（在庫・出品・販売マスター）
- シート2: store_master（仕入先店舗マスタ）
- シート3: template_master（定型文テンプレートマスタ）
- 古物営業法に基づく古物台帳（受入・払出）フォーマット整形機能
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from services.id_generator import get_next_available_ids

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
MOCK_DIR = BASE_DIR / "data" / "mock"

INVENTORY_COLUMNS = [
    "item_id",
    "purchase_date",
    "supplier_name",
    "product_name",
    "category",
    "cost_price",
    "serial_number",
    "condition_rank",
    "accessories",
    "notes",
    "receipt_total",
    "generated_description",
    "status",
    "sales_date",
    "sales_price",
    "platform_fee",
    "shipping_cost",
    "net_profit",
]

STORE_COLUMNS = ["store_name"]

TEMPLATE_COLUMNS = [
    "template_id",
    "template_name",
    "intro_text",
    "outro_text",
    "prompt_notes",
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsService:
    """
    GoogleスプレッドシートとローカルモックCSVを透過的に扱うデータサービス。
    接続情報が存在しない場合や認証エラー時は自動的に `data/mock/*.csv` へフォールバックします。
    """

    def __init__(self) -> None:
        self.spreadsheet_id: Optional[str] = self._resolve_spreadsheet_id()
        self.service_account_info_or_path = self._resolve_service_account()
        self.client = None
        self.spreadsheet = None
        self.is_connected: bool = False
        self.connection_message: str = ""

        self._ensure_mock_files()
        self._connect_if_configured()

    def _resolve_spreadsheet_id(self) -> Optional[str]:
        env_id = os.getenv("SPREADSHEET_ID", "").strip()
        if env_id and env_id != "your_spreadsheet_id_here":
            return env_id
        try:
            if "SPREADSHEET_ID" in st.secrets:
                sec_id = str(st.secrets["SPREADSHEET_ID"]).strip()
                if sec_id and sec_id != "your_spreadsheet_id_here":
                    return sec_id
        except Exception:
            pass
        return None

    def _resolve_service_account(self) -> Optional[Any]:
        env_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        if env_path and env_path != "path/to/service_account.json":
            return env_path
        try:
            if "GOOGLE_SERVICE_ACCOUNT_JSON" in st.secrets:
                val = st.secrets["GOOGLE_SERVICE_ACCOUNT_JSON"]
                if isinstance(val, str) and val.strip() != "path/to/service_account.json":
                    return val.strip()
                elif hasattr(val, "to_dict") or isinstance(val, dict):
                    return dict(val)
            if "gcp_service_account" in st.secrets:
                return dict(st.secrets["gcp_service_account"])
        except Exception:
            pass
        return None

    def _ensure_mock_files(self) -> None:
        MOCK_DIR.mkdir(parents=True, exist_ok=True)
        inv_path = MOCK_DIR / "inventory.csv"
        if not inv_path.exists():
            pd.DataFrame(columns=INVENTORY_COLUMNS).to_csv(inv_path, index=False, encoding="utf-8-sig")

        store_path = MOCK_DIR / "store_master.csv"
        if not store_path.exists():
            pd.DataFrame(
                {"store_name": ["セカンドストリート廿日市店", "セカンドストリート広島五日市店"]}
            ).to_csv(store_path, index=False, encoding="utf-8-sig")

        tmpl_path = MOCK_DIR / "template_master.csv"
        if not tmpl_path.exists():
            pd.DataFrame(columns=TEMPLATE_COLUMNS).to_csv(tmpl_path, index=False, encoding="utf-8-sig")

    def _connect_if_configured(self) -> None:
        if not self.spreadsheet_id or not self.service_account_info_or_path:
            self.is_connected = False
            self.connection_message = "ローカルモックモード（data/mock/*.csv を使用中）"
            return

        try:
            import gspread
            from google.oauth2.service_account import Credentials

            if isinstance(self.service_account_info_or_path, dict):
                creds = Credentials.from_service_account_info(
                    self.service_account_info_or_path, scopes=SCOPES
                )
            else:
                path_str = str(self.service_account_info_or_path)
                if path_str.startswith("{"):
                    info = json.loads(path_str)
                    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
                else:
                    if not Path(path_str).exists():
                        self.is_connected = False
                        self.connection_message = (
                            f"サービスアカウントJSONが見つかりません ({path_str})。ローカルモックで動作中。"
                        )
                        return
                    creds = Credentials.from_service_account_file(path_str, scopes=SCOPES)

            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self._ensure_worksheets()
            self.is_connected = True
            self.connection_message = f"Googleスプレッドシート接続済み ({self.spreadsheet.title})"
        except Exception as e:
            self.is_connected = False
            self.connection_message = f"Google Sheets未接続（モックCSV動作中）: {e}"

    def _ensure_worksheets(self) -> None:
        """必要な3つのシートが存在しない場合はヘッダー付きで自動作成します。"""
        if not self.spreadsheet:
            return
        existing_titles = [ws.title for ws in self.spreadsheet.worksheets()]

        for title, headers in [
            ("inventory", INVENTORY_COLUMNS),
            ("store_master", STORE_COLUMNS),
            ("template_master", TEMPLATE_COLUMNS),
        ]:
            if title not in existing_titles:
                ws = self.spreadsheet.add_worksheet(title=title, rows=500, cols=len(headers))
                ws.append_row(headers, value_input_option="USER_ENTERED")
            else:
                ws = self.spreadsheet.worksheet(title)
                first_row = ws.row_values(1)
                if not first_row:
                    ws.append_row(headers, value_input_option="USER_ENTERED")

    def get_spreadsheet_url(self) -> Optional[str]:
        """連携先GoogleスプレッドシートのURLを返します。未設定時はNone。"""
        if self.spreadsheet_id:
            return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"
        return None

    # =========================================================================
    # シート1: inventory 操作
    # =========================================================================
    def get_inventory_df(self) -> pd.DataFrame:
        if self.is_connected and self.spreadsheet:
            try:
                ws = self.spreadsheet.worksheet("inventory")
                records = ws.get_all_records()
                df = pd.DataFrame(records)
                for col in INVENTORY_COLUMNS:
                    if col not in df.columns:
                        df[col] = ""
                return df[INVENTORY_COLUMNS].fillna("")
            except Exception:
                pass

        inv_path = MOCK_DIR / "inventory.csv"
        try:
            df = pd.read_csv(inv_path, dtype=str).fillna("")
            for col in INVENTORY_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            return df[INVENTORY_COLUMNS]
        except Exception:
            return pd.DataFrame(columns=INVENTORY_COLUMNS)

    def get_next_item_ids(self, count: int = 1) -> List[str]:
        """既存の inventory シートを走査し、未使用の最小Base32番号を count 個返します。"""
        df = self.get_inventory_df()
        existing_ids = df["item_id"].astype(str).tolist() if "item_id" in df.columns else []
        return get_next_available_ids(existing_ids, count=count)

    def append_inventory_items(self, items: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        1件または複数件（まとめ売りセット）の仕入・出品データを inventory に追記します。
        また、新規の仕入先店舗名が含まれていれば store_master へ自動登録します。
        """
        if not items:
            return False, "登録する商品データがありません。"

        # 新規店舗の自動マスタ登録チェック
        for item in items:
            supplier = str(item.get("supplier_name", "")).strip()
            if supplier:
                self.ensure_store_in_master(supplier)

        rows_to_add = []
        for item in items:
            row_dict = {col: item.get(col, "") for col in INVENTORY_COLUMNS}
            if not row_dict.get("status"):
                row_dict["status"] = "出品中"
            rows_to_add.append([row_dict[col] for col in INVENTORY_COLUMNS])

        if self.is_connected and self.spreadsheet:
            try:
                ws = self.spreadsheet.worksheet("inventory")
                ws.append_rows(rows_to_add, value_input_option="USER_ENTERED")
                return True, f"Googleスプレッドシート（inventory）へ {len(rows_to_add)} 件記帳しました。"
            except Exception as e:
                return False, f"Googleスプレッドシートへの書き込みに失敗しました: {e}"

        # ローカルモックCSVへの追記
        try:
            df = self.get_inventory_df()
            new_df = pd.DataFrame(rows_to_add, columns=INVENTORY_COLUMNS)
            updated_df = pd.concat([df, new_df], ignore_index=True)
            updated_df.to_csv(MOCK_DIR / "inventory.csv", index=False, encoding="utf-8-sig")
            return True, f"ローカルモック（data/mock/inventory.csv）へ {len(rows_to_add)} 件記帳しました。"
        except Exception as e:
            return False, f"ローカルモックCSVへの保存に失敗しました: {e}"

    # =========================================================================
    # シート2: store_master 操作
    # =========================================================================
    def get_stores(self) -> List[str]:
        if self.is_connected and self.spreadsheet:
            try:
                ws = self.spreadsheet.worksheet("store_master")
                values = ws.col_values(1)
                stores = [v.strip() for v in values[1:] if v and v.strip()]
                return list(dict.fromkeys(stores))
            except Exception:
                pass

        store_path = MOCK_DIR / "store_master.csv"
        try:
            df = pd.read_csv(store_path, dtype=str).fillna("")
            if "store_name" in df.columns:
                stores = [s.strip() for s in df["store_name"].tolist() if s.strip()]
                return list(dict.fromkeys(stores))
        except Exception:
            pass
        return ["セカンドストリート廿日市店", "セカンドストリート広島五日市店"]

    def ensure_store_in_master(self, store_name: str) -> bool:
        """
        既存マスタにない新規店舗名が指定された場合、store_master の末尾へ自動追記します。
        追記した場合は True、既に存在する場合は False を返します。
        """
        clean_name = store_name.strip()
        if not clean_name:
            return False

        existing_stores = self.get_stores()
        if clean_name in existing_stores:
            return False

        if self.is_connected and self.spreadsheet:
            try:
                ws = self.spreadsheet.worksheet("store_master")
                ws.append_row([clean_name], value_input_option="USER_ENTERED")
                return True
            except Exception:
                pass

        # モックCSVへ追記
        store_path = MOCK_DIR / "store_master.csv"
        new_list = existing_stores + [clean_name]
        pd.DataFrame({"store_name": new_list}).to_csv(store_path, index=False, encoding="utf-8-sig")
        return True

    # =========================================================================
    # シート3: template_master 操作
    # =========================================================================
    def get_templates_df(self) -> pd.DataFrame:
        if self.is_connected and self.spreadsheet:
            try:
                ws = self.spreadsheet.worksheet("template_master")
                records = ws.get_all_records()
                df = pd.DataFrame(records)
                for col in TEMPLATE_COLUMNS:
                    if col not in df.columns:
                        df[col] = ""
                return df[TEMPLATE_COLUMNS].fillna("")
            except Exception:
                pass

        tmpl_path = MOCK_DIR / "template_master.csv"
        try:
            df = pd.read_csv(tmpl_path, dtype=str).fillna("")
            for col in TEMPLATE_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            return df[TEMPLATE_COLUMNS]
        except Exception:
            return pd.DataFrame(columns=TEMPLATE_COLUMNS)

    def add_template(
        self,
        template_name: str,
        intro_text: str,
        outro_text: str,
        prompt_notes: str,
    ) -> Tuple[bool, str, str]:
        """
        新しい定型文テンプレートを template_master へ追記します。
        Returns: (success, message, new_template_id)
        """
        clean_name = template_name.strip()
        if not clean_name:
            return False, "テンプレート名を入力してください。", ""

        df = self.get_templates_df()
        next_num = len(df) + 1
        existing_ids = set(df["template_id"].astype(str).tolist()) if not df.empty else set()
        while f"T{next_num:02d}" in existing_ids:
            next_num += 1
        new_id = f"T{next_num:02d}"

        new_row = [
            new_id,
            clean_name,
            intro_text.strip(),
            outro_text.strip(),
            prompt_notes.strip(),
        ]

        if self.is_connected and self.spreadsheet:
            try:
                ws = self.spreadsheet.worksheet("template_master")
                ws.append_row(new_row, value_input_option="USER_ENTERED")
                return True, f"テンプレート「{clean_name}」({new_id}) をスプレッドシートに保存しました。", new_id
            except Exception as e:
                return False, f"スプレッドシートへのテンプレート保存に失敗しました: {e}", ""

        try:
            new_df = pd.DataFrame([new_row], columns=TEMPLATE_COLUMNS)
            updated_df = pd.concat([df, new_df], ignore_index=True)
            updated_df.to_csv(MOCK_DIR / "template_master.csv", index=False, encoding="utf-8-sig")
            return True, f"テンプレート「{clean_name}」({new_id}) を保存しました。", new_id
        except Exception as e:
            return False, f"テンプレート保存に失敗しました: {e}", ""

    def _save_templates_df(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """template_master 全体を上書き保存します（更新・削除用）。"""
        clean_df = df[TEMPLATE_COLUMNS].fillna("")
        if self.is_connected and self.spreadsheet:
            try:
                ws = self.spreadsheet.worksheet("template_master")
                ws.clear()
                rows = [TEMPLATE_COLUMNS] + clean_df.values.tolist()
                ws.update(rows, value_input_option="USER_ENTERED")
                return True, "スプレッドシートのテンプレートマスタを更新しました。"
            except Exception as e:
                return False, f"スプレッドシートの更新に失敗しました: {e}"

        try:
            clean_df.to_csv(MOCK_DIR / "template_master.csv", index=False, encoding="utf-8-sig")
            return True, "テンプレートマスタを更新しました。"
        except Exception as e:
            return False, f"テンプレートマスタの保存に失敗しました: {e}"

    def update_template(
        self,
        template_id: str,
        template_name: str,
        intro_text: str,
        outro_text: str,
        prompt_notes: str,
    ) -> Tuple[bool, str]:
        """既存テンプレートの名前（リネーム）および文面を上書き更新します。"""
        clean_name = template_name.strip()
        if not clean_name:
            return False, "テンプレート名を入力してください。"

        df = self.get_templates_df()
        if df.empty or template_id not in df["template_id"].astype(str).values:
            return False, f"対象のテンプレート ({template_id}) が見つかりません。"

        mask = df["template_id"].astype(str) == str(template_id)
        df.loc[mask, "template_name"] = clean_name
        df.loc[mask, "intro_text"] = intro_text.strip()
        df.loc[mask, "outro_text"] = outro_text.strip()
        df.loc[mask, "prompt_notes"] = prompt_notes.strip()

        ok, msg = self._save_templates_df(df)
        if ok:
            return True, f"テンプレート「{clean_name}」({template_id}) を更新しました。"
        return False, msg

    def delete_template(self, template_id: str) -> Tuple[bool, str]:
        """指定された template_id のテンプレートを削除します。"""
        df = self.get_templates_df()
        if df.empty or template_id not in df["template_id"].astype(str).values:
            return False, f"対象のテンプレート ({template_id}) が見つかりません。"

        target_name = df.loc[df["template_id"].astype(str) == str(template_id), "template_name"].iloc[0]
        updated_df = df[df["template_id"].astype(str) != str(template_id)].reset_index(drop=True)

        ok, msg = self._save_templates_df(updated_df)
        if ok:
            return True, f"テンプレート「{target_name}」({template_id}) を削除しました。"
        return False, msg

    # =========================================================================
    # 古物台帳フォーマット変換
    # =========================================================================
    def get_kobutsu_ledger_df(
        self,
        keyword: str = "",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        inventory シートのデータを古物営業法様式に準拠した台帳ビュー（受入・払出）へ整形して返します。
        - 受入: 管理番号, 受入年月日, 取引区別(買受), 品目(商品名・型番), 特徴（製造番号等）, 数量, 代価(仕入原価), 相手方(仕入先店舗)
        - 払出: ステータス, 払出年月日(販売日), 払出対価(販売価格)
        """
        df = self.get_inventory_df()
        if df.empty:
            return pd.DataFrame(
                columns=[
                    "管理番号",
                    "受入年月日",
                    "取引区別",
                    "品目（商品名・型番）",
                    "特徴（製造番号等）",
                    "数量",
                    "受入代価（税込）",
                    "相手方（仕入先店舗）",
                    "ステータス",
                    "払出年月日",
                    "払出対価（販売価格）",
                ]
            )

        # フィルタリング処理
        filtered = df.copy()

        if keyword and keyword.strip():
            kw = keyword.strip().lower()
            mask = (
                filtered["item_id"].astype(str).str.lower().str.contains(kw, na=False)
                | filtered["product_name"].astype(str).str.lower().str.contains(kw, na=False)
                | filtered["serial_number"].astype(str).str.lower().str.contains(kw, na=False)
                | filtered["supplier_name"].astype(str).str.lower().str.contains(kw, na=False)
            )
            filtered = filtered[mask]

        if date_from:
            filtered = filtered[filtered["purchase_date"].astype(str) >= date_from]
        if date_to:
            filtered = filtered[filtered["purchase_date"].astype(str) <= date_to]

        def _fmt_yen(val: Any) -> str:
            s = str(val).strip()
            if not s:
                return "-"
            try:
                num = int(float(s))
                return f"¥{num:,}"
            except ValueError:
                return s

        def _fmt_feature(row: pd.Series) -> str:
            sn = str(row.get("serial_number", "")).strip()
            rank = str(row.get("condition_rank", "")).strip()
            if sn and rank:
                return f"{sn} [{rank}]"
            return sn or rank or "-"

        ledger = pd.DataFrame(
            {
                "管理番号": filtered["item_id"],
                "受入年月日": filtered["purchase_date"],
                "取引区別": "買受（店舗仕入）",
                "品目（商品名・型番）": filtered["product_name"],
                "特徴（製造番号等）": filtered.apply(_fmt_feature, axis=1),
                "数量": 1,
                "受入代価（税込）": filtered["cost_price"].apply(_fmt_yen),
                "相手方（仕入先店舗）": filtered["supplier_name"],
                "ステータス": filtered["status"].replace("", "出品中"),
                "払出年月日": filtered["sales_date"].replace("", "-"),
                "払出対価（販売価格）": filtered["sales_price"].apply(_fmt_yen),
            }
        )
        return ledger.reset_index(drop=True)
