from typing import Optional


def normalize_horse_number(raw: Optional[str]) -> Optional[str]:
    """
    horsepia 등록번호(마번)를 7자리로 정규화한다.
    과거 프로젝트에서 확인된 "엑셀에서 선행 0이 소실되는" 이슈를 방지하기 위함.
    빈 값/None은 그대로 None으로 둔다 (마번은 선택 입력 항목).
    """
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned:
        return None
    if cleaned.endswith(".0"):
        cleaned = cleaned[:-2]
    if not cleaned.isdigit():
        return cleaned
    return cleaned.zfill(7)