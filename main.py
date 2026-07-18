"""
NiceGUI 앱 엔트리포인트.
현재 등록된 화면: main_page(조회), manage_page(관리), dashboard_page(대시보드).
"""
from nicegui import ui

from ui import main_page  # noqa: F401  (@ui.page 데코레이터 등록을 위한 import)
from ui import manage_page  # noqa: F401
from ui import dashboard_page  # noqa: F401
from ui.theme import apply_global_theme


@ui.page("/")
def index() -> None:
    apply_global_theme()
    ui.navigate.to("/main")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Jeju_farm_horse", host="0.0.0.0", port=8080, reload=False)