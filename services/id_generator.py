"""
Base32英数字圧縮採番モジュール

視覚的・OCRで誤読しやすい文字（0, O, 1, I）を除外した32種類の英数字を用いた
3桁採番（#222 〜 #ZZZ、全32,768通り）を提供します。
"""

from typing import Iterable, List, Set

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
BASE = len(ALPHABET)  # 32
CODE_LENGTH = 3
MAX_VALUE = (BASE ** CODE_LENGTH) - 1  # 32767


def encode_base32(num: int) -> str:
    """
    0〜32767の整数を '#XXX' 形式のBase32管理番号にエンコードします。
    例: 0 -> '#222', 1 -> '#223', 32767 -> '#ZZZ'
    """
    if not (0 <= num <= MAX_VALUE):
        raise ValueError(f"採番範囲外です: {num} (許容範囲: 0〜{MAX_VALUE})")

    chars = []
    temp = num
    for _ in range(CODE_LENGTH):
        temp, rem = divmod(temp, BASE)
        chars.append(ALPHABET[rem])
    chars.reverse()
    return "#" + "".join(chars)


def decode_base32(item_id: str) -> int:
    """
    '#XXX' または 'XXX' 形式のBase32管理番号を整数（0〜32767）にデコードします。
    無効な文字や桁数の場合は ValueError を送出します。
    """
    if not item_id:
        raise ValueError("空のitem_idです")

    clean_id = item_id.strip().upper()
    if clean_id.startswith("#"):
        clean_id = clean_id[1:]

    if len(clean_id) != CODE_LENGTH:
        raise ValueError(f"管理番号の桁数が不正です: {item_id}")

    value = 0
    for ch in clean_id:
        idx = ALPHABET.find(ch)
        if idx == -1:
            raise ValueError(f"使用できない文字 '{ch}' が含まれています: {item_id}")
        value = value * BASE + idx
    return value


def is_valid_item_id(item_id: str) -> bool:
    """指定された文字列が有効なBase32管理番号形式かどうかを判定します。"""
    try:
        decode_base32(item_id)
        return True
    except ValueError:
        return False


def get_next_available_ids(existing_ids: Iterable[str], count: int = 1) -> List[str]:
    """
    既存の管理番号一覧を走査し、未使用の最小番号から順番に count 個の採番リストを返します。
    既存の番号に Base32 以外の形式（例: 旧形式の '#A01' など）が含まれていても、
    正規化した文字列セットとして重複回避しつつ、有効な32進数（#222〜#ZZZ）の最小空き番号を割り当てます。
    """
    if count <= 0:
        return []

    used_numbers: Set[int] = set()
    used_raw_strings: Set[str] = set()

    for raw_id in existing_ids:
        if not raw_id:
            continue
        norm = str(raw_id).strip().upper()
        if not norm.startswith("#"):
            norm = "#" + norm
        used_raw_strings.add(norm)
        try:
            num = decode_base32(norm)
            used_numbers.add(num)
        except ValueError:
            # 0, O, 1, I を含むレガシーID等は数値セットからはスキップし文字列一致で保護
            pass

    result: List[str] = []
    candidate_num = 0
    while len(result) < count and candidate_num <= MAX_VALUE:
        candidate_id = encode_base32(candidate_num)
        if candidate_num not in used_numbers and candidate_id not in used_raw_strings:
            result.append(candidate_id)
            used_numbers.add(candidate_num)
            used_raw_strings.add(candidate_id)
        candidate_num += 1

    if len(result) < count:
        raise RuntimeError("利用可能な管理番号（32,768通り）が枯渇しました。")

    return result
