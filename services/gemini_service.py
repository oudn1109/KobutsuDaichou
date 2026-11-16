"""
Gemini API連携および出品説明文生成モジュール

構造化プロンプトを用いて、冒頭文・本文（AI整理）・末尾文・管理番号を結合した
信頼性の高いメルカリ出品説明文を生成します。
APIキー未設定時やエラー発生時にはルールベースのローカル整形フォールバックを提供します。
"""

import os
from typing import Any, Dict, List, Optional, Tuple
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "gemini-2.5-flash"


def get_gemini_api_key() -> Optional[str]:
    """環境変数または st.secrets から GEMINI_API_KEY を取得します。"""
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key and api_key != "your_gemini_api_key_here":
        return api_key.strip()

    try:
        if "GEMINI_API_KEY" in st.secrets:
            secret_key = str(st.secrets["GEMINI_API_KEY"]).strip()
            if secret_key and secret_key != "your_gemini_api_key_here":
                return secret_key
    except Exception:
        pass

    return None


def build_body_prompt(
    items: List[Dict[str, Any]],
    prompt_notes: str = "",
    is_bundle: bool = False,
) -> str:
    """
    Geminiに【本文】セクションのみを生成させるための構造化プロンプトを組み立てます。
    冒頭文・末尾文・管理番号はコード側で厳密に固定配置するため、Geminiには本文部分のみを出力させます。
    """
    bundle_instruction = (
        "今回は複数商品の【まとめ売りセット出品】です。各商品のスペック・状態・付属品が混同されないよう、"
        "商品ごとに見やすく整理して記載してください。"
        if is_bundle
        else "今回は1点ものの単品出品です。商品の魅力と状態が購入者に正確に伝わるよう整理して記載してください。"
    )

    items_text_blocks = []
    for idx, item in enumerate(items, start=1):
        prefix = f"【商品{idx}】\n" if is_bundle else "【商品情報】\n"
        condition = item.get("condition_rank", "目立った傷や汚れなし")
        block = (
            f"{prefix}"
            f"- 商品名・型番: {item.get('product_name', '未入力')}\n"
            f"- 商品の状態: {condition}\n"
            f"- シリアルナンバー・特徴: {item.get('serial_number', '特になし')}\n"
            f"- 付属品: {item.get('accessories', 'なし（本体のみ）')}\n"
            f"- 動作確認・状態メモ: {item.get('notes', '特になし')}"
        )
        items_text_blocks.append(block)

    items_section = "\n\n".join(items_text_blocks)
    extra_notes_section = (
        f"\n【カテゴリ特有の追加指示（prompt_notes）】\n{prompt_notes.strip()}\n"
        if prompt_notes and prompt_notes.strip()
        else ""
    )

    prompt = f"""あなたはメルカリで高い評価を得ている誠実な個人出品者です。
以下の入力データに基づき、出品説明文の【本文パート（商品概要、商品の状態・動作確認、付属品）】のみを作成してください。

※冒頭の挨拶文、末尾の発送案内、および最下部の管理番号はシステム側で自動結合するため、あなたの出力には絶対に含めないでください。

## 厳守すべき生成ルール
1. **トーン＆マナー**: メルカリで信頼される誠実・清潔感のある個人の出品者トーンで記述してください。
2. **禁止事項**:
   - 業者感のある絵文字の多用、★や☆などの記号装飾、「絶対お得！」「早い者勝ち！」「超極上品！」といった誇大広告は**完全禁止**です。「■」や「・」などのシンプルで見やすい記号のみを使用してください。
   - **独自ランク記号の完全禁止**: 商品説明文の中に「ランクS」「ランクA」「ランクB」「状態ランク：A」といった業者風の独自ランク記号は**絶対に出力しないでください**。メルカリ公式の「商品の状態」（例：目立った傷や汚れなし、やや傷や汚れあり 等）の表現をそのまま用いてください。
3. **ハルシネーション（捏造）の厳格な防止**:
   - 入力データに記載されていない付属品、スペック、動作保証を勝手に推測・創作しないでください。
   - 付属品欄に書かれていないもの（箱や説明書など）は「付属する」と絶対に書かず、入力された付属品のみを記載してください（「箱なし」等の入力があれば欠品状況を正直に明記してください）。
4. **シリアル番号の扱い**:
   - 入力された製造番号/シリアルが固有の識別番号である場合、盗用防止のため全文ではなく一部伏字にするか外観特徴を中心に清潔感をもって記載するか、購入者が安心できる形で整理してください。
5. **出品形態**: {bundle_instruction}
{extra_notes_section}
## 入力された商品データ
{items_section}

## 出力フォーマット構成例
■ 商品名
（商品名・型番・カラーを見やすく記載）

■ 商品の状態
（メルカリ公式の「商品の状態」と、動作確認メモや特徴・キズ等を箇条書きで正直かつ丁寧に記載。※「ランクA」「ランクB」等の記号は絶対に使わないこと）

■ 付属品
（入力された付属品のみを正確に記載。記載のないものは捏造しないこと）
"""
    return prompt


def format_fallback_body(items: List[Dict[str, Any]], is_bundle: bool = False) -> str:
    """
    APIキー未設定時やオフライン時に、入力情報からルールベースで清潔な【本文】を構築します。
    """
    if not is_bundle and len(items) == 1:
        item = items[0]
        product_name = item.get("product_name") or "（商品名未入力）"
        condition = item.get("condition_rank") or "目立った傷や汚れなし"
        serial_number = item.get("serial_number") or ""
        accessories = item.get("accessories") or "本体のみ（記載の付属品なし）"
        notes = item.get("notes") or "基本的な外観確認および簡易清掃済みです。"

        detail_lines = [f"・状態区分：{condition}"]
        if notes.strip():
            for line in notes.strip().splitlines():
                clean_line = line.strip().lstrip("・- ")
                if clean_line:
                    detail_lines.append(f"・{clean_line}")
        if serial_number.strip():
            detail_lines.append(f"・個体情報/特徴：{serial_number.strip()}")

        details_text = "\n".join(detail_lines)

        return (
            f"■ 商品名\n{product_name}\n\n"
            f"■ 商品の状態・動作確認内容\n{details_text}\n\n"
            f"■ 付属品\n・{accessories.strip()}\n※写真および上記に記載のあるものが全てとなります。"
        )

    # まとめ売りセット出品の場合
    sections = ["■ セット内容一覧"]
    for idx, item in enumerate(items, start=1):
        product_name = item.get("product_name") or f"商品{idx}"
        condition = item.get("condition_rank") or "目立った傷や汚れなし"
        serial_number = item.get("serial_number") or "特記事項なし"
        accessories = item.get("accessories") or "本体のみ"
        notes = item.get("notes") or "確認済み"
        sections.append(
            f"【{idx}. {product_name}】\n"
            f"・商品の状態：{condition}\n"
            f"・外観/動作詳細：{notes.strip()}\n"
            f"・特徴/識別情報：{serial_number.strip()}\n"
            f"・付属品：{accessories.strip()}"
        )
    sections.append("※各商品の付属品は上記および写真に掲載されているものが全てとなります。")
    return "\n\n".join(sections)


def assemble_full_description(
    intro_text: str,
    body_text: str,
    outro_text: str,
    item_ids: List[str],
) -> str:
    """
    【冒頭】・【本文】・【末尾】・【最下部の管理番号】を仕様通りに結合します。
    最下部のフォーマット:
      単品: 管理番号: [#XXX]
      まとめ売り: 管理番号: [#XXX, #YYY]
    """
    parts = []
    if intro_text and intro_text.strip():
        parts.append(intro_text.strip())

    if body_text and body_text.strip():
        parts.append(body_text.strip())

    if outro_text and outro_text.strip():
        parts.append(outro_text.strip())

    formatted_ids = ", ".join(item_ids)
    parts.append(f"管理番号: [{formatted_ids}]")

    return "\n\n".join(parts)


def generate_listing_description(
    items: List[Dict[str, Any]],
    intro_text: str,
    outro_text: str,
    prompt_notes: str,
    item_ids: List[str],
    is_bundle: bool = False,
) -> Tuple[str, bool, str]:
    """
    Gemini API (`gemini-2.5-flash`) を呼び出して出品説明文を生成します。

    Returns:
        Tuple[generated_text, used_gemini_api, status_message]
    """
    api_key = get_gemini_api_key()
    prompt = build_body_prompt(items=items, prompt_notes=prompt_notes, is_bundle=is_bundle)

    if not api_key:
        fallback_body = format_fallback_body(items=items, is_bundle=is_bundle)
        full_text = assemble_full_description(intro_text, fallback_body, outro_text, item_ids)
        return (
            full_text,
            False,
            "GEMINI_API_KEY が未設定のため、ローカル整形モードで出品文を作成しました。",
        )

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        body_text = (response.text or "").strip()
        if body_text:
            full_text = assemble_full_description(intro_text, body_text, outro_text, item_ids)
            return full_text, True, f"Gemini API ({MODEL_NAME}) で出品説明文を生成しました。"
    except ImportError:
        try:
            import google.generativeai as legacy_genai  # type: ignore

            legacy_genai.configure(api_key=api_key)
            model = legacy_genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(prompt)
            body_text = (response.text or "").strip()
            if body_text:
                full_text = assemble_full_description(intro_text, body_text, outro_text, item_ids)
                return full_text, True, f"Gemini API ({MODEL_NAME} / legacy SDK) で出品説明文を生成しました。"
        except Exception as e:
            fallback_body = format_fallback_body(items=items, is_bundle=is_bundle)
            full_text = assemble_full_description(intro_text, fallback_body, outro_text, item_ids)
            return (
                full_text,
                False,
                f"Gemini API呼び出しエラーのためローカル整形にフォールバックしました: {e}",
            )
    except Exception as e:
        fallback_body = format_fallback_body(items=items, is_bundle=is_bundle)
        full_text = assemble_full_description(intro_text, fallback_body, outro_text, item_ids)
        return (
            full_text,
            False,
            f"Gemini API呼び出しエラーのためローカル整形にフォールバックしました: {e}",
        )

    fallback_body = format_fallback_body(items=items, is_bundle=is_bundle)
    full_text = assemble_full_description(intro_text, fallback_body, outro_text, item_ids)
    return full_text, False, "空の応答が返されたためローカル整形モードで生成しました。"
