"""
화면 상단 공용 네비게이션 (아키텍처 프롬프트 6장 "레이아웃" 참고).
조회/관리/대시보드 화면을 이동하고, 현재 위치를 강조 표시한다.
"""
from __future__ import annotations

from nicegui import ui

from ui.theme import apply_global_theme

_PAGES = [
    ("/main", "조회"),
    ("/manage", "관리"),
    ("/dashboard", "대시보드"),
]


def render_nav(active_path: str) -> None:
    apply_global_theme()
    with ui.row().classes("w-full gap-6 mb-2 border-b border-gray-200 pb-2"):
        for path, label in _PAGES:
            classes = "text-sm no-underline"
            if path == active_path:
                classes += " font-medium text-primary border-b-2 border-primary pb-2"
            else:
                classes += " text-gray-500"
            ui.link(label, path).classes(classes)