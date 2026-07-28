"""
좌측 드로어(drawer) 공용 네비게이션.
- PC(넓은 화면, breakpoint 이상): show-if-above로 항상 열림
- 모바일(좁은 화면): 기본 닫힌 상태, 햄버거 아이콘으로 열고 닫음
"""
from __future__ import annotations

from nicegui import ui

from ui.theme import apply_global_theme


_PAGES = [
    ("/dashboard", "대시보드", "bar_chart"),
    ("/main", "조회", "search"),
    ("/manage", "관리", "edit_note"),
    (None, None, None),
    ("/entrustment", "위탁관리", "assignment"),
    ("/auction", "경매관리", "gavel"),
    ("/racing", "경주성적", "flag"),
]


def render_nav(active_path: str):
    apply_global_theme()

    with ui.header().classes(
        "items-center justify-between bg-white text-gray-700 border-b border-gray-200 px-2"
    ).style("box-shadow: none;"):
        with ui.row().classes("items-center gap-1"):
            drawer_toggle = ui.button(icon="menu").props("flat round dense color=grey-8")
            with ui.row().classes("items-center gap-2"):
                ui.icon("pets").classes("text-primary text-xl")
                ui.label("제주목장").classes("text-lg font-bold")

    with ui.left_drawer().classes(
        "bg-white border-r border-gray-200 px-3 py-4 gap-1"
    ).props("bordered show-if-above breakpoint=1024") as drawer:
        drawer_toggle.on("click", drawer.toggle)

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

    content = ui.column().classes("w-full p-6 gap-6")
    return content