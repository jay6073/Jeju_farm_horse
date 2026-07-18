"""
NiceGUI 앱 엔트리포인트.
지금은 3단계(조회 화면) 검증용으로 main_page만 등록한다.
manage_page, dashboard_page가 만들어지면 여기에 같이 등록하고 네비게이션을 추가한다.
"""
from nicegui import ui

from ui import main_page  # noqa: F401  (@ui.page 데코레이터 등록을 위한 import)


@ui.page("/")
def index() -> None:
    ui.navigate.to("/main")


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Jeju_farm_horse", reload=False)