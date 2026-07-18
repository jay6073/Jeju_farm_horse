"""
조회 화면 (아키텍처 프롬프트 4-1절).

- 마종 select → 마명 select(오늘 기준 상태='정상'인 말만) 캐스케이딩
- 마명 선택 시 버튼 없이 자동으로 스크래핑 트리거 (UI 블로킹 없이 run.io_bound)
- 품종코드가 없는 말은 자동탐지(get_horse_detail_auto)로 처리
- 스크래핑 실패는 ScrapingError만 잡아 친절한 에러 메시지로 표시
- /main?horse_id=42 형태의 딥링크 지원 (대시보드 목록의 하이퍼링크에서 진입)
"""
from __future__ import annotations

import asyncio
from typing import Optional

from nicegui import run, ui

from models.horse import HORSE_SPECIES, Horse
from repository.horse_repository import HorseRepository
from services import scraping_service
from services.scraping_service import ScrapingError
from ui.nav import render_nav
from ui.theme import CARD_CLASSES

_repo = HorseRepository()


@ui.page("/main")
async def main_page(horse_id: Optional[int] = None) -> None:
    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-6"):
        render_nav("/main")
        ui.label("보유마 조회").classes("text-xl font-medium")

        with ui.row().classes("w-full gap-3"):
            species_select = ui.select(
                options=HORSE_SPECIES, label="마종"
            ).classes("flex-1")
            horse_select = ui.select(options={}, label="마명").classes("flex-1")
            horse_select.disable()

        result_container = ui.column().classes("w-full")

        def render_empty_state(message: str, icon: str = "search") -> None:
            result_container.clear()
            with result_container:
                with ui.column().classes(
                    "w-full items-center gap-2 py-8 text-gray-400 bg-gray-50 rounded-lg"
                ):
                    ui.icon(icon).classes("text-3xl")
                    ui.label(message).classes("text-sm")

        def render_error(message: str) -> None:
            result_container.clear()
            with result_container:
                with ui.row().classes(
                    "w-full items-center gap-2 py-4 px-4 bg-red-50 rounded-lg"
                ):
                    ui.icon("error").classes("text-red-500")
                    ui.label(message).classes("text-red-600 text-sm")

        def render_loading() -> None:
            result_container.clear()
            with result_container:
                with ui.row().classes("w-full items-center gap-2 py-8 justify-center"):
                    ui.spinner(size="lg")
                    ui.label("마적사항을 불러오는 중...").classes("text-gray-500 text-sm")

        def render_horse_card(horse: Horse, basic_info: dict[str, str]) -> None:
            result_container.clear()
            with result_container:
                with ui.card().classes(CARD_CLASSES + " p-4"):
                    with ui.row().classes("items-center gap-2 mb-2"):
                        ui.icon("pets").classes("text-primary")
                        ui.label(horse.마명).classes("text-lg font-medium")
                        ui.badge(horse.마종).classes("ml-auto")
                    for label, value in basic_info.items():
                        with ui.row().classes(
                            "w-full justify-between text-sm py-1 border-b border-gray-100"
                        ):
                            ui.label(label).classes("text-gray-500")
                            ui.label(value)

        async def load_and_render(horse: Horse) -> None:
            render_loading()
            try:
                if horse.품종코드:
                    data = await run.io_bound(
                        scraping_service.get_horse_detail_for, horse
                    )
                else:
                    data = await run.io_bound(
                        scraping_service.get_horse_detail_auto, horse, _repo
                    )
            except ScrapingError as e:
                render_error(str(e))
                return

            if data is None:
                # NiceGUI의 run.io_bound은 작업이 취소되거나(페이지 이탈 등) 앱 종료 중이면
                # 예외 대신 None을 반환한다(공식 문서화된 동작). 이 경우 보여줄 화면도
                # 없고 사용자도 이미 없을 가능성이 높으니 조용히 종료한다.
                return

            basic_info = scraping_service.extract_basic_info(
                data, hrs_gb_cd=horse.품종코드
            )
            try:
                render_horse_card(horse, basic_info)
            except RuntimeError:
                # 스크래핑 도중 사용자가 페이지를 떠나 화면(슬롯) 자체가 사라진 경우.
                # 보여줄 대상이 없으니 조용히 무시한다.
                pass

        def update_horse_options() -> None:
            species = species_select.value
            result_container.clear()
            if not species:
                horse_select.set_options({})
                horse_select.disable()
                return

            horses = _repo.get_active_names_by_species(species)
            horse_select.set_options({h.id: h.마명 for h in horses})
            horse_select.value = None
            if horses:
                horse_select.enable()
                render_empty_state("마명을 선택하면 마적사항이 표시됩니다")
            else:
                horse_select.disable()
                render_empty_state(f"{species}에 해당하는 보유마가 없습니다", icon="info")

        async def on_horse_selected() -> None:
            horse_id = horse_select.value
            if horse_id is None:
                return
            horse = _repo.get_by_id(horse_id)
            if horse is None:
                render_error("선택한 말 정보를 찾을 수 없습니다.")
                return
            await load_and_render(horse)

        species_select.on_value_change(update_horse_options)
        horse_select.on_value_change(on_horse_selected)

        render_empty_state("마종을 먼저 선택하세요")

        # ---- 딥링크 지원: /main?horse_id=42 ----
        # 스크래핑(외부 네트워크)이 끝날 때까지 페이지 응답 자체를 막으면 안 되므로,
        # select 값 세팅까지만 동기로 하고 실제 조회는 백그라운드 태스크로 흘려보낸다.
        # (마명 select의 on_change와 동일한 방식 — 페이지가 이미 뜬 뒤 갱신되는 구조)
        if horse_id is not None:
            horse = _repo.get_by_id(horse_id)
            if horse is not None:
                species_select.value = horse.마종
                update_horse_options()
                horse_select.value = horse.id
                asyncio.create_task(load_and_render(horse))
            else:
                render_error(f"horse_id={horse_id}에 해당하는 말을 찾을 수 없습니다.")