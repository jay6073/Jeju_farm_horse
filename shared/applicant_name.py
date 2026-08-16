from __future__ import annotations

import re
from typing import Optional

_MISSING = "(신청인 미상)"


def normalize_applicant_name(name: Optional[str]) -> str:
    """
    신청인 표기를 집계 키로 정규화한다.
    ㈜ 와 (주) 를 같은 회사로 보고, 공백 차이도 무시한다.
    빈 값은 '(신청인 미상)'으로 둔다.
    """
    text = "" if name is None else str(name).strip()
    if not text:
        return _MISSING
    text = text.replace("㈜", "(주)")
    return re.sub(r"\s+", "", text)
