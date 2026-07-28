"""
좌측 사이드바 공용 네비게이션 (아키텍처 프롬프트 6장 "레이아웃" 참고).
"""
from __future__ import annotations

from nicegui import ui

from ui.theme import apply_global_theme


_PAGES = [
    ("/dashboard", "대시보드", "bar_chart"),
    ("/main", "조회", "search"),
    ("/manage", "관리", "edit_note"),
    (None, None, None),  # 구분선
    ("/entrustment", "위탁관리", "assignment"),
    ("/auction", "경매관리", "gavel"),
    ("/racing", "경주성적", "flag"),
]


def render_nav(active_path: str):
    """사이드바를 렌더링하고, 페이지 콘텐츠를 넣을 컨테이너를 반환한다."""
    apply_global_theme()

    row = ui.row().classes("w-full h-screen -m-6 gap-0")
    row.__enter__()

    with ui.column().classes(
        "w-52 h-full flex-shrink-0 bg-white border-r border-gray-200 px-3 py-4 gap-1"
    ):
        with ui.row().classes("items-center gap-2 px-2 mb-4"):
            ui.icon("pets").classes("text-primary text-xl")
            ui.label("제주목장").classes("text-lg font-bold text-gray-700")

        for path, label, icon in _PAGES:
            if path is None:
                ui.separator().classes("my-2")
                continue

            is_active = path == active_path
            classes = (
                "w-full px-3 py-2 rounded-md no-underline "
                "transition-colors hover:bg-gray-100 flex items-center"
            )
            classes += (
                " text-primary font-medium bg-primary/10 hover:bg-primary/15"
                if is_active
                else " text-gray-500"
            )
            with ui.link(target=path).classes(classes):
                with ui.row().classes("items-center gap-2"):
                    ui.icon(icon).classes("text-base")
                    ui.label(label).classes("text-sm")

    content = ui.column().classes("flex-1 h-full overflow-y-auto p-6 gap-6")
    row.__exit__(None, None, None)

    return content