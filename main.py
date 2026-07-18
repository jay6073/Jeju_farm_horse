"""
NiceGUI 앱 엔트리포인트.
현재 등록된 화면: main_page(조회), manage_page(관리).
dashboard_page(5단계)가 만들어지면 여기에 import 추가 + ui/nav.py의 _PAGES에도 등록한다.
"""
from nicegui import ui

from ui import main_page  # noqa: F401  (@ui.page 데코레이터 등록을 위한 import)
from ui import manage_page  # noqa: F401


@ui.page("/")
def index() -> None:
    ui.navigate.to("/main")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Jeju_farm_horse", reload=False)