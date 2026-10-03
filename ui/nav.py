"""
좌측 드로어(drawer) 공용 네비게이션 (아코디언 방식).
- 하위 메뉴가 여러 개인 그룹(보유마, 위탁·경매)은 접고 펼칠 수 있다.
- 현재 페이지가 속한 그룹은 처음부터 펼쳐진 상태로 시작한다.
- 대시보드·예산비교·인력현황은 바로 이동하는 링크다.
- PC(넓은 화면, breakpoint 이상): show-if-above로 항상 열림
- 모바일(좁은 화면): 기본 닫힌 상태, 햄버거 아이콘으로 열고 닫음

메뉴 구성을 바꾸려면 아래 _MENU만 고치면 된다.
각 페이지는 render_nav("/경로")만 호출하므로 다른 파일은 수정할 필요가 없다.
"""
from __future__ import annotations

from nicegui import ui

from ui.theme import apply_global_theme

# 메뉴 항목 형식
#   ("link",  경로, 이름, 아이콘)                 바로 이동하는 링크
#   ("group", 이름, 아이콘, [(경로, 이름, 아이콘), ...])   접고 펴는 그룹
#   ("sep",)                                       구분선
_MENU = [
    ("link", "/dashboard", "대시보드", "bar_chart"),
    ("sep",),
    ("group", "보유마", "list_alt", [
        ("/main", "조회", "search"),
        ("/manage", "관리", "edit_note"),
        ("/print", "명단출력", "print"),
        ("/holding", "보유현황", "grid_view"),
    ]),
    ("sep",),
    ("group", "위탁·경매", "gavel", [
        ("/entrustment", "위탁관리", "assignment"),
        ("/auction", "경매관리", "gavel"),
        ("/racing", "경주성적", "flag"),
        ("/profile", "통합조회", "folder_shared"),
    ]),
    ("sep",),
    ("link", "/budget-compare", "예산비교", "compare_arrows"),
    ("sep",),
    ("link", "/staff", "인력현황", "badge"),
]

_NAV_CSS = """
.nav-group .q-item { min-height: 40px; padding: 0 12px; border-radius: 6px; }
.nav-group .q-item__section--avatar { min-width: 28px; }
.nav-group .q-item:hover { background: #f3f4f6; }
"""

_LINK_BASE = (
    "w-full px-3 py-2 rounded-md no-underline "
    "transition-colors hover:bg-gray-100 flex items-center"
)


def _link_classes(is_active: bool) -> str:
    if is_active:
        return _LINK_BASE + " text-primary font-medium bg-primary/10 hover:bg-primary/15"
    return _LINK_BASE + " text-gray-500"


def _render_link(path: str, label: str, icon: str, active_path: str) -> None:
    with ui.link(target=path).classes(_link_classes(path == active_path)):
        with ui.row().classes("items-center gap-2"):
            ui.icon(icon).classes("text-base")
            ui.label(label).classes("text-sm")


def _render_group(name: str, icon: str, items: list, active_path: str) -> None:
    contains_active = any(path == active_path for path, _, _ in items)
    header_cls = "text-sm " + (
        "text-gray-800 font-medium" if contains_active else "text-gray-500"
    )
    with ui.expansion(name, icon=icon, value=contains_active).classes(
        "w-full nav-group"
    ).props(f'dense dense-toggle header-class="{header_cls}"'):
        with ui.column().classes("w-full gap-1 pl-4 ml-4 border-l border-gray-200"):
            for path, label, item_icon in items:
                _render_link(path, label, item_icon, active_path)


def render_nav(active_path: str):
    apply_global_theme()
    ui.add_css(_NAV_CSS)

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

        for entry in _MENU:
            kind = entry[0]
            if kind == "sep":
                ui.separator().classes("my-2")
            elif kind == "link":
                _, path, label, icon = entry
                _render_link(path, label, icon, active_path)
            elif kind == "group":
                _, name, icon, items = entry
                _render_group(name, icon, items, active_path)

    content = ui.column().classes("w-full p-6 gap-6")
    return content