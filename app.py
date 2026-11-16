"""
古物商対応・物販管理Webアプリ（Streamlit）
視線が上から下へ一直線（I字型）に流れる2ステップ・シンプルUI
- 普段の出品導線（STEP 1 -> STEP 2）には「テンプレートを選ぶ」「商品説明文出力・台帳記入」だけを配置
- テンプレートの管理（編集・リネーム / 新規作成 / 削除）は専用ダイアログへ分離し、タブで目的別に明確化
"""

import datetime
import json
from typing import Any, Dict, List
import streamlit as st
import streamlit.components.v1 as components

from services.gemini_service import generate_listing_description, get_gemini_api_key
from services.sheets_service import SheetsService

st.set_page_config(
    page_title="物販・古物台帳管理",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        display: none;
    }

    /* 第1階層：ページ全体の背景（清潔感のある淡いライトグレー） */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"] {
        background-color: #f1f5f9 !important;
        color: #0f172a !important;
    }

    .block-container {
        max-width: 660px;
        padding-top: 2.2rem;
        padding-bottom: 5rem;
    }

    /* 第2階層：STEP 1 / STEP 2 のカード本体（純白カード＋上部ブルーライン） */
    .st-key-step1_card,
    .st-key-step2_card {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-top: 5px solid #2563eb !important;
        border-radius: 12px !important;
        padding: 1.8rem 2rem !important;
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06) !important;
    }

    /* 第3階層：カード内の各入力フィールド */
    .st-key-step1_card div[data-baseweb="input"] > div,
    .st-key-step1_card div[data-baseweb="select"] > div,
    .st-key-step1_card div[data-baseweb="textarea"] > div,
    .st-key-step1_card div[data-testid="stNumberInputContainer"],
    .st-key-step2_card div[data-baseweb="input"] > div,
    .st-key-step2_card div[data-baseweb="select"] > div,
    .st-key-step2_card div[data-baseweb="textarea"] > div {
        background-color: #f8fafc !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }

    /* 入力フォーカス時は純白＋青枠 */
    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="select"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within {
        background-color: #ffffff !important;
        border-color: #2563eb !important;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15) !important;
    }

    /* ラベル（項目見出し） */
    label[data-testid="stWidgetLabel"] p {
        font-size: 0.88rem !important;
        font-weight: 700 !important;
        color: #1e293b !important;
        margin-bottom: 2px !important;
    }

    /* 自動採番・変更不可の管理番号フィールド */
    input:disabled {
        background-color: #e2e8f0 !important;
        color: #0f172a !important;
        font-weight: 800 !important;
        font-size: 0.98rem !important;
        -webkit-text-fill-color: #0f172a !important;
        opacity: 1 !important;
    }

    /* ステップ見出し */
    .step-marker {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 1.12rem;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 1.2rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #e2e8f0;
    }
    .step-badge {
        background-color: #2563eb;
        color: #ffffff;
        font-size: 0.75rem;
        font-weight: 800;
        padding: 3px 9px;
        border-radius: 6px;
        letter-spacing: 0.04em;
    }

    /* ステップ間の余白スペース */
    .step-spacer {
        height: 2.2rem;
    }

    /* ヘッダーのステータス表示 */
    .status-pill {
        display: inline-block;
        background: #ffffff;
        color: #475569;
        border: 1px solid #cbd5e1;
        padding: 3px 10px;
        border-radius: 999px;
        font-weight: 600;
        font-size: 0.76rem;
        margin-left: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# メルカリ公式の「商品の状態」と同じ並び順（デフォルト選択は index=2「目立った傷や汚れなし」）
MERCARI_CONDITIONS = [
    "新品、未使用",
    "未使用に近い",
    "目立った傷や汚れなし",
    "やや傷や汚れあり",
    "傷や汚れあり",
    "全体的に状態が悪い（ジャンク）",
]
DEFAULT_CONDITION_INDEX = 2  # 目立った傷や汚れなし


def get_sheets_service() -> SheetsService:
    if "sheets_service" not in st.session_state:
        st.session_state.sheets_service = SheetsService()
    return st.session_state.sheets_service


def render_copy_button(text_to_copy: str) -> None:
    """ワンクリックでクリップボードへコピーするボタン"""
    escaped_json = json.dumps(text_to_copy)
    html_code = f"""
    <div style="margin: 2px 0;">
        <button id="copy-btn" style="
            width: 100%;
            padding: 0.65rem 1rem;
            background-color: #ffffff;
            color: #0f172a;
            border: 1px solid #cbd5e1;
            border-radius: 0.5rem;
            font-size: 0.92rem;
            font-weight: 700;
            cursor: pointer;
            transition: background-color 0.15s ease;
        " onmouseover="this.style.backgroundColor='#f1f5f9'" onmouseout="this.style.backgroundColor='#ffffff'">
            出品文をコピーする
        </button>
        <div id="copy-msg" style="
            font-size: 0.8rem;
            color: #2563eb;
            margin-top: 4px;
            text-align: center;
            height: 1.1rem;
            font-weight: 600;
        "></div>
    </div>
    <script>
    const btn = document.getElementById('copy-btn');
    const msg = document.getElementById('copy-msg');
    const text = {escaped_json};
    btn.addEventListener('click', async () => {{
        try {{
            await navigator.clipboard.writeText(text);
            msg.textContent = 'コピーしました';
            setTimeout(() => {{ msg.textContent = ''; }}, 2500);
        }} catch (err) {{
            const ta = document.createElement('textarea');
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            msg.textContent = 'コピーしました';
            setTimeout(() => {{ msg.textContent = ''; }}, 2500);
        }}
    }});
    </script>
    """
    components.html(html_code, height=68)


@st.dialog("古物台帳", width="large")
def open_kobutsu_ledger_dialog(service: SheetsService) -> None:
    """古物台帳（受入・払出）のモーダル表示"""
    f_col1, f_col2 = st.columns([3, 2])
    with f_col1:
        keyword = st.text_input(
            "検索",
            placeholder="管理番号・品名・製造番号・仕入先",
            key="ledger_kw",
        )
    with f_col2:
        date_from_val = st.date_input(
            "仕入日（以降）",
            value=None,
            key="ledger_date_from",
        )

    date_from_str = date_from_val.strftime("%Y-%m-%d") if date_from_val else None

    ledger_df = service.get_kobutsu_ledger_df(
        keyword=keyword,
        date_from=date_from_str,
        date_to=None,
    )

    st.dataframe(
        ledger_df,
        use_container_width=True,
        hide_index=True,
        height=380,
    )

    b_col1, b_col2 = st.columns(2)
    with b_col1:
        if not ledger_df.empty:
            csv_bytes = ledger_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="CSVダウンロード",
                data=csv_bytes,
                file_name=f"kobutsu_ledger_{datetime.date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with b_col2:
        sheet_url = service.get_spreadsheet_url()
        if sheet_url:
            st.link_button(
                "スプレッドシート原本を開く",
                url=sheet_url,
                use_container_width=True,
            )


@st.dialog("定型文テンプレート管理", width="large")
def open_template_manager_dialog(service: SheetsService, initial_template_id: str = "") -> None:
    """
    テンプレートの「編集・リネーム」「新規作成」「削除」という性質の異なる3つの操作を、
    タブで完全に分離して誤操作なく直感的に行える専用モーダルダイアログ。
    """
    templates_df = service.get_templates_df()
    template_options = {
        f"{row['template_id']}: {row['template_name']}": row
        for _, row in templates_df.iterrows()
    }
    option_labels = list(template_options.keys())

    default_idx = 0
    for idx, lbl in enumerate(option_labels):
        if str(template_options[lbl]["template_id"]) == str(initial_template_id):
            default_idx = idx
            break

    tab_edit, tab_create, tab_delete = st.tabs(
        ["既存テンプレートの編集・リネーム", "新規テンプレート作成", "テンプレートの削除"]
    )

    with tab_edit:
        if not option_labels:
            st.info("登録されているテンプレートがありません。「新規テンプレート作成」タブから追加してください。")
        else:
            target_label = st.selectbox(
                "編集するテンプレートを選択",
                options=option_labels,
                index=default_idx,
                key="dlg_edit_select",
            )
            target_row = template_options[target_label]
            tid = str(target_row["template_id"])

            new_name = st.text_input(
                "テンプレート名（変更するとリネームされます）",
                value=str(target_row["template_name"]),
                key=f"dlg_edit_name_{tid}",
            )
            new_intro = st.text_area(
                "冒頭文",
                value=str(target_row["intro_text"]),
                height=85,
                key=f"dlg_edit_intro_{tid}",
            )
            new_outro = st.text_area(
                "末尾文",
                value=str(target_row["outro_text"]),
                height=85,
                key=f"dlg_edit_outro_{tid}",
            )
            new_notes = st.text_area(
                "AIへの追加指示",
                value=str(target_row["prompt_notes"]),
                height=70,
                key=f"dlg_edit_notes_{tid}",
            )

            if st.button("変更内容を上書き保存する", type="primary", use_container_width=True, key="dlg_btn_update"):
                ok, msg = service.update_template(
                    template_id=tid,
                    template_name=new_name,
                    intro_text=new_intro,
                    outro_text=new_outro,
                    prompt_notes=new_notes,
                )
                if ok:
                    st.session_state.selected_template_id = tid
                    st.toast(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with tab_create:
        create_name = st.text_input(
            "新しいテンプレート名",
            key="dlg_create_name",
        )
        create_intro = st.text_area(
            "冒頭文",
            height=85,
            key="dlg_create_intro",
        )
        create_outro = st.text_area(
            "末尾文",
            height=85,
            key="dlg_create_outro",
        )
        create_notes = st.text_area(
            "AIへの追加指示",
            height=70,
            key="dlg_create_notes",
        )

        if st.button("新規テンプレートとして登録する", type="primary", use_container_width=True, key="dlg_btn_create"):
            ok, msg, new_tid = service.add_template(
                template_name=create_name,
                intro_text=create_intro,
                outro_text=create_outro,
                prompt_notes=create_notes,
            )
            if ok:
                st.session_state.selected_template_id = new_tid
                st.toast(msg)
                st.rerun()
            else:
                st.error(msg)

    with tab_delete:
        if not option_labels:
            st.info("削除できるテンプレートがありません。")
        else:
            del_label = st.selectbox(
                "削除するテンプレートを選択",
                options=option_labels,
                index=default_idx,
                key="dlg_del_select",
            )
            del_row = template_options[del_label]
            del_tid = str(del_row["template_id"])

            st.caption(f"選択中: {del_row['template_name']} ({del_tid})")
            if st.button("このテンプレートを削除する", use_container_width=True, key="dlg_btn_delete"):
                ok, msg = service.delete_template(del_tid)
                if ok:
                    st.session_state.selected_template_id = None
                    st.toast(msg)
                    st.rerun()
                else:
                    st.error(msg)


def initialize_session_state(service: SheetsService) -> None:
    if "bundle_count" not in st.session_state:
        st.session_state.bundle_count = 2
    if "generated_description" not in st.session_state:
        st.session_state.generated_description = ""
    if "last_recorded_msg" not in st.session_state:
        st.session_state.last_recorded_msg = ""
    if "selected_template_id" not in st.session_state:
        st.session_state.selected_template_id = None

    templates_df = service.get_templates_df()
    if not templates_df.empty and st.session_state.selected_template_id is None:
        st.session_state.selected_template_id = str(templates_df.iloc[0]["template_id"])


def render_store_selector(stores: List[str], key_prefix: str, label: str = "仕入先店舗") -> str:
    options = stores + ["＋ 新規店舗を入力"]
    selected = st.selectbox(label, options=options, key=f"{key_prefix}_store_select")
    if selected == "＋ 新規店舗を入力":
        custom_store = st.text_input(
            "新規店舗名",
            key=f"{key_prefix}_store_custom",
        )
        return custom_store.strip()
    return selected


def render_single_vertical_inputs(stores: List[str], assigned_id: str) -> Dict[str, Any]:
    """通常（1点出品）：見出しのみ・左揃え縦1列"""
    st.text_input(
        "管理番号",
        value=assigned_id,
        disabled=True,
        key="single_item_id_display",
    )

    purchase_date = st.date_input(
        "仕入日",
        value=datetime.date.today(),
        key="single_purchase_date",
    )

    supplier_name = render_store_selector(stores, key_prefix="single", label="仕入先店舗")

    cost_price = st.number_input(
        "仕入原価",
        min_value=0,
        max_value=10_000_000,
        value=3000,
        step=100,
        key="single_cost_price",
    )

    product_name = st.text_input(
        "商品名・型番",
        key="single_product_name",
    )

    condition = st.selectbox(
        "商品の状態",
        options=MERCARI_CONDITIONS,
        index=DEFAULT_CONDITION_INDEX,
        key="single_condition_rank",
    )

    serial_number = st.text_input(
        "シリアルナンバー・特徴",
        key="single_serial_number",
    )

    accessories = st.text_input(
        "付属品",
        key="single_accessories",
    )

    notes = st.text_area(
        "動作確認・状態メモ",
        height=90,
        key="single_notes",
    )

    return {
        "item_id": assigned_id,
        "purchase_date": purchase_date.strftime("%Y-%m-%d"),
        "supplier_name": supplier_name,
        "product_name": product_name.strip(),
        "category": "",
        "cost_price": cost_price,
        "serial_number": serial_number.strip(),
        "condition_rank": condition,
        "accessories": accessories.strip(),
        "notes": notes.strip(),
        "receipt_total": "",
        "status": "出品中",
    }


def render_bundle_vertical_inputs(stores: List[str], assigned_ids: List[str]) -> List[Dict[str, Any]]:
    """まとめ売り（セット出品）：見出しのみ・左揃え縦1列"""
    items_data: List[Dict[str, Any]] = []

    for idx in range(st.session_state.bundle_count):
        item_id = assigned_ids[idx]
        if idx > 0:
            st.divider()
        st.markdown(f"**品目 {idx + 1}**")

        st.text_input(
            "管理番号",
            value=item_id,
            disabled=True,
            key=f"bundle_{idx}_id_display",
        )

        p_date = st.date_input(
            "仕入日",
            value=datetime.date.today(),
            key=f"bundle_{idx}_date",
        )

        supplier = render_store_selector(stores, key_prefix=f"bundle_{idx}", label="仕入先店舗")

        cost = st.number_input(
            "仕入原価",
            min_value=0,
            max_value=10_000_000,
            value=1500,
            step=100,
            key=f"bundle_{idx}_cost",
        )

        p_name = st.text_input(
            "商品名・型番",
            key=f"bundle_{idx}_name",
        )

        condition = st.selectbox(
            "商品の状態",
            options=MERCARI_CONDITIONS,
            index=DEFAULT_CONDITION_INDEX,
            key=f"bundle_{idx}_rank",
        )

        serial = st.text_input(
            "シリアルナンバー・特徴",
            key=f"bundle_{idx}_serial",
        )

        acc = st.text_input(
            "付属品",
            key=f"bundle_{idx}_acc",
        )

        note = st.text_area(
            "動作確認・状態メモ",
            height=75,
            key=f"bundle_{idx}_note",
        )

        items_data.append(
            {
                "item_id": item_id,
                "purchase_date": p_date.strftime("%Y-%m-%d"),
                "supplier_name": supplier,
                "product_name": p_name.strip(),
                "category": "",
                "cost_price": cost,
                "serial_number": serial.strip(),
                "condition_rank": condition,
                "accessories": acc.strip(),
                "notes": note.strip(),
                "receipt_total": "",
                "status": "出品中",
            }
        )

    st.write("")
    if st.button("＋ 商品枠を追加", use_container_width=True):
        st.session_state.bundle_count += 1
        st.rerun()
    if st.session_state.bundle_count > 2:
        if st.button("－ 最後の商品枠を削除", use_container_width=True):
            st.session_state.bundle_count = max(2, st.session_state.bundle_count - 1)
            st.rerun()

    return items_data


def main() -> None:
    service = get_sheets_service()
    initialize_session_state(service)
    sheet_url = service.get_spreadsheet_url()

    # =========================================================================
    # ヘッダーエリア
    # =========================================================================
    h_col1, h_col2, h_col3 = st.columns([2.6, 1.2, 1.2])
    with h_col1:
        st.markdown("### 物販・古物台帳管理")
    with h_col2:
        if st.button("古物台帳を開く", use_container_width=True):
            open_kobutsu_ledger_dialog(service)
    with h_col3:
        if sheet_url:
            st.link_button("シート原本", url=sheet_url, use_container_width=True)
        else:
            if st.button("再読込", use_container_width=True):
                st.session_state.sheets_service = SheetsService()
                st.rerun()

    db_badge = "Sheets連携中" if service.is_connected else "ローカル保存"
    ai_badge = "Gemini連携中" if get_gemini_api_key() else "自動整形モード"
    st.markdown(
        f'<div style="text-align:right; margin-bottom: 1.2rem;">'
        f'<span class="status-pill">{db_badge}</span><span class="status-pill">{ai_badge}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    # =========================================================================
    # STEP 1: 仕入・商品情報の入力
    # =========================================================================
    with st.container(border=True, key="step1_card"):
        st.markdown(
            '<div class="step-marker"><span class="step-badge">STEP 1</span><span>仕入・商品情報の入力</span></div>',
            unsafe_allow_html=True,
        )

        listing_mode = st.radio(
            "出品タイプ",
            options=["通常（1点出品）", "まとめ売り（セット出品）"],
            horizontal=True,
            key="listing_mode_radio",
        )
        is_bundle = listing_mode == "まとめ売り（セット出品）"
        required_id_count = st.session_state.bundle_count if is_bundle else 1
        assigned_ids = service.get_next_item_ids(count=required_id_count)
        ids_str = ", ".join(assigned_ids)

        stores = service.get_stores()
        if not is_bundle:
            items_data = [render_single_vertical_inputs(stores, assigned_ids[0])]
        else:
            items_data = render_bundle_vertical_inputs(stores, assigned_ids)

    # ステップ間のスペース
    st.markdown('<div class="step-spacer"></div>', unsafe_allow_html=True)

    # =========================================================================
    # STEP 2: テンプレート選択・商品説明文出力・台帳記入
    # =========================================================================
    with st.container(border=True, key="step2_card"):
        st.markdown(
            '<div class="step-marker"><span class="step-badge">STEP 2</span><span>テンプレート選択・商品説明文出力・台帳記入</span></div>',
            unsafe_allow_html=True,
        )

        templates_df = service.get_templates_df()
        current_tmpl_id = ""
        intro_text = ""
        outro_text = ""
        prompt_notes = ""

        t_col1, t_col2 = st.columns([3.4, 1.2], vertical_alignment="bottom")
        with t_col1:
            if not templates_df.empty:
                template_options = {
                    f"{row['template_id']}: {row['template_name']}": row
                    for _, row in templates_df.iterrows()
                }
                option_labels = list(template_options.keys())

                default_idx = 0
                for idx, lbl in enumerate(option_labels):
                    if str(template_options[lbl]["template_id"]) == str(st.session_state.selected_template_id):
                        default_idx = idx
                        break

                selected_label = st.selectbox(
                    "定型文テンプレート",
                    options=option_labels,
                    index=default_idx,
                )
                selected_row = template_options[selected_label]
                current_tmpl_id = str(selected_row["template_id"])
                st.session_state.selected_template_id = current_tmpl_id
                intro_text = str(selected_row["intro_text"])
                outro_text = str(selected_row["outro_text"])
                prompt_notes = str(selected_row["prompt_notes"])
            else:
                st.selectbox("定型文テンプレート", options=["テンプレート未登録"], disabled=True)

        with t_col2:
            if st.button("テンプレート管理", use_container_width=True):
                open_template_manager_dialog(service, initial_template_id=current_tmpl_id)

        st.write("")
        # ボタン文言を「商品説明文出力・台帳記入」にシンプル化
        if st.button(
            f"商品説明文出力・台帳記入 ({ids_str})",
            type="primary",
            use_container_width=True,
        ):
            missing_names = [
                f"品目{i+1}" for i, item in enumerate(items_data) if not item.get("product_name")
            ]
            missing_stores = [
                f"品目{i+1}" for i, item in enumerate(items_data) if not item.get("supplier_name")
            ]
            if missing_names:
                st.error(f"{', '.join(missing_names)} の「商品名・型番」を入力してください。")
            elif missing_stores:
                st.error(f"{', '.join(missing_stores)} の「仕入先店舗」を入力してください。")
            else:
                with st.spinner("出力・記入中..."):
                    gen_text, _, _ = generate_listing_description(
                        items=items_data,
                        intro_text=intro_text,
                        outro_text=outro_text,
                        prompt_notes=prompt_notes,
                        item_ids=assigned_ids,
                        is_bundle=is_bundle,
                    )
                    st.session_state.generated_description = gen_text

                    records_to_save = []
                    for item in items_data:
                        record = dict(item)
                        record["generated_description"] = gen_text
                        record["status"] = "出品中"
                        record["sales_date"] = ""
                        record["sales_price"] = ""
                        record["platform_fee"] = ""
                        record["shipping_cost"] = ""
                        record["net_profit"] = ""
                        records_to_save.append(record)

                    ok, msg = service.append_inventory_items(records_to_save)
                    if ok:
                        st.session_state.last_recorded_msg = f"商品説明文を出力し、台帳へ記入しました（管理番号: {ids_str}）"
                        st.rerun()
                    else:
                        st.error(msg)

        if st.session_state.last_recorded_msg:
            st.success(st.session_state.last_recorded_msg)

        edited_description = st.text_area(
            "出品説明文",
            value=st.session_state.generated_description,
            height=300,
        )
        st.session_state.generated_description = edited_description

        if edited_description.strip():
            render_copy_button(edited_description)
        else:
            st.button(
                "出品文をコピーする",
                disabled=True,
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
