"""
화면 상단 공용 헤더/네비게이션 (아키텍처 프롬프트 6장 "레이아웃" 참고).
앱 브랜딩(로고+이름)을 콘텐츠 영역과 시각적으로 분리하고, 조회/관리/대시보드를
아이콘과 함께 이동하며, 현재 위치를 강조 표시한다.
"""
from __future__ import annotations

from nicegui import ui

from ui.theme import apply_global_theme

_PAGES = [
    ("/main", "조회", "search"),
    ("/manage", "관리", "edit_note"),
    ("/dashboard", "대시보드", "bar_chart"),
]


def render_nav(active_path: str) -> None:
    apply_global_theme()

    # 헤더 바 — 콘텐츠 영역과 분리되는 브랜딩 영역
    with ui.row().classes(
        "w-full items-center gap-2 -mx-6 -mt-6 px-6 py-3 mb-4 "
        "bg-white border-b border-gray-200"
    ):
        ui.icon("pets").classes("text-primary text-xl")
        ui.label("제주목장 보유마 관리").classes("text-xl font-bold text-gray-700")

        with ui.row().classes("ml-auto gap-1"):
            for path, label, icon in _PAGES:
                is_active = path == active_path
                classes = "px-3 py-1.5 rounded-md no-underline transition-colors hover:bg-gray-100"
                classes += (
                    " text-primary font-medium bg-primary/10 hover:bg-primary/15"
                    if is_active
                    else " text-gray-500"
                )
                with ui.link(target=path).classes(classes):
                    with ui.row().classes("items-center gap-1"):
                        ui.icon(icon).classes("text-base")
                        ui.label(label).classes("text-sm")