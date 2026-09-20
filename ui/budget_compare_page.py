"""예산 비교 화면 — budget-compare 정적 프로그램을 iframe으로 임베드."""

from nicegui import ui

from ui.nav import render_nav
from ui.theme import apply_global_theme

# 헤더 높이(px). 하단이 잘리거나 빈 띠가 생기면 이 값만 조정
HEADER_HEIGHT_PX = 47


@ui.page("/budget-compare")
def budget_compare_page() -> None:
    apply_global_theme()
    content = render_nav("/budget-compare")

    ui.query(".nicegui-content").classes("p-0 gap-0")
    content.classes(replace="w-full p-0 gap-0")

    with content:
        ui.element("iframe").props(
            'src="/apps/budget-compare/index.html" title="예산 비교"'
        ).classes("w-full border-0").style(
            f"height: calc(100vh - {HEADER_HEIGHT_PX}px)"
        )
