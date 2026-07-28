"""
좌측 드로어(drawer) 공용 네비게이션 (아키텍처 프롬프트 6장 "레이아웃" 참고).

- PC(넓은 화면): 사이드바가 항상 고정되어 열려있음
- 모바일(좁은 화면, 기본 브레이크포인트 1023px 미만): 자동으로 오버레이 드로어로 전환,
  상단 헤더의 햄버거 아이콘으로 열고 닫음 (ui.left_drawer의 기본 반응형 동작)
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
    """상단 헤더 + 좌측 드로어를 렌더링하고, 페이지 콘텐츠를 넣을 컨테이너를 반환한다."""
    apply_global_theme()

    with ui.header().classes(
        "items-center justify-between bg-white text-gray-700 border-b border-gray-200 px-2"
    ).style("box-shadow: none;"):
        with ui.row().classes("items-center gap-1"):
            drawer_toggle = ui.button(icon="menu").props("flat round dense color=grey-8")
            with ui.row().classes("items-center gap-2"):
                ui.icon("pets").classes("text-primary text-xl")
                ui.label("제주목장").classes("text-lg font-bold")

    with ui.left_drawer(value=True).classes(
        "bg-white border-r border-gray-200 px-3 py-4 gap-1"
    ).props("bordered") as drawer:
        drawer_toggle.on("click", drawer.toggle)

        def close_drawer_if_mobile() -> None:
            ui.run_javascript(
                f"if (window.innerWidth < 1024) {{ getElement({drawer.id}).hide(); }}",
                respond=False,
            )

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
            with ui.link(target=path).classes(classes) as link:
                with ui.row().classes("items-center gap-2"):
                    ui.icon(icon).classes("text-base")
                    ui.label(label).classes("text-sm")
                link.on("click", close_drawer_if_mobile)

    content = ui.column().classes("w-full p-6 gap-6")
    return content