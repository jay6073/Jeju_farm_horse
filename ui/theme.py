"""
공용 디자인 토큰 (아키텍처 프롬프트 6장 "디자인 가이드라인").

색상은 최소화한다 — 브랜드 컬러 1개(포인트 컬러) + 회색 계열이 기본이고,
상태 뱃지에만 의미 있는 색을 쓴다. 카드는 flat 배경 + 얇은 보더로 통일한다.
"""
from __future__ import annotations

from nicegui import ui

PRIMARY_COLOR = "#1c64f2"

# 페이지/섹션 공통 여백 규칙 (좌우 패딩 24px, 섹션 간격 24px, 카드 내부 16px)
PAGE_CLASSES = "w-full mx-auto p-6 gap-6"
CARD_CLASSES = "w-full rounded-lg border border-gray-200 shadow-none"

_STATUS_BADGE_STYLE: dict[str, str] = {
    "정상": "bg-green-100 text-green-700",
    "폐사": "bg-gray-200 text-gray-600",
    "위수탁종료": "bg-gray-200 text-gray-600",
    "매각": "bg-gray-200 text-gray-600",
    "기타": "bg-orange-100 text-orange-700",
}


def apply_global_theme() -> None:
    """앱 시작 시(main.py) 한 번만 호출한다."""
    ui.colors(primary=PRIMARY_COLOR)
    ui.add_head_html(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
        <style>
          body, .q-field, .q-btn, .q-item { font-family: 'Noto Sans KR', sans-serif; }
        </style>
        """
    )


def status_badge(status: str) -> None:
    """상태값에 맞는 색의 pill 뱃지 하나를 렌더링한다."""
    style = _STATUS_BADGE_STYLE.get(status, "bg-gray-200 text-gray-600")
    ui.label(status).classes(f"text-xs px-2 py-0.5 rounded-full {style} inline-block")