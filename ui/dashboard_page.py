"""
대시보드 화면 (아키텍처 프롬프트 4-3절).

- 오늘 기준(상태='정상') 마종별 두수 카드 5개 + 합계 카드
- 카드 아래 전체 보유마 목록: 마번 / 마명 / 마종 / 상태(+상태발생일자)
- 마명 검색창, 마명은 ui.link로 렌더링해 /main?horse_id=로 딥링크
"""
from __future__ import annotations

from nicegui import run, ui

from models.horse import HORSE_SPECIES
from repository.horse_repository import HorseRepository
from services import dashboard_service
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state, status_badge

_repo = HorseRepository()


@ui.page("/dashboard")
async def dashboard_page() -> None:
    with ui.column().classes("w-full max-w-3xl mx-auto p-6 gap-6"):
        render_nav("/dashboard")
        ui.label("보유두수 대시보드").classes("text-xl font-medium")

        counts = await run.io_bound(dashboard_service.get_species_counts, _repo)
        total = sum(counts.values())

        with ui.row().classes("w-full gap-3 flex-wrap"):
            _render_count_card("합계", total, highlight=True)
            for species in HORSE_SPECIES:
                _render_count_card(species, counts.get(species, 0))

        ui.separator()

        search_input = ui.input(label="마명 검색").classes("w-full max-w-xs")
        list_container = ui.column().classes("w-full")

        all_horses = await run.io_bound(dashboard_service.get_all_horses, _repo)

        def render_list(filter_text: str = "") -> None:
            list_container.clear()
            filter_text = (filter_text or "").strip()
            filtered = [
                h for h in all_horses if not filter_text or filter_text in h.마명
            ]
            with list_container:
                if not filtered:
                    empty_state("조건에 맞는 보유마가 없습니다", icon="search_off")
                    return
                with ui.card().classes(CARD_CLASSES + " p-4"):
                    with ui.row().classes(
                        "w-full text-xs text-gray-400 font-medium bg-gray-50 rounded-t-md "
                        "px-2 py-1 -mt-4 -mx-4 mb-2"
                    ):
                        ui.label("마번").classes("w-28")
                        ui.label("마명").classes("flex-1")
                        ui.label("마종").classes("w-24")
                        ui.label("상태").classes("w-44")
                    for h in filtered:
                        with ui.row().classes(
                            "w-full items-center text-sm py-1.5 px-1 -mx-1 rounded "
                            "border-b border-gray-100 transition-colors hover:bg-gray-50"
                        ):
                            ui.label(h.마번 or "-").classes("w-28 text-gray-500")
                            ui.link(h.마명, f"/main?horse_id={h.id}").classes(
                                "flex-1 text-primary no-underline"
                            )
                            ui.label(h.마종).classes("w-24")
                            with ui.row().classes("w-44 items-center gap-2"):
                                status_badge(h.상태)
                                if h.상태 != "정상" and h.상태발생일자:
                                    ui.label(h.상태발생일자).classes(
                                        "text-xs text-gray-400"
                                    )

        search_input.on_value_change(lambda e: render_list(e.value))
        render_list()


def _render_count_card(label: str, count: int, highlight: bool = False) -> None:
    box_classes = "rounded-lg p-4 gap-1 border"
    box_classes += " bg-primary/10 border-primary/20" if highlight else " bg-gray-50 border-gray-200"
    text_classes = "text-2xl font-medium"
    if highlight:
        text_classes += " text-primary"
    with ui.column().classes(box_classes).style("min-width: 90px;"):
        ui.label(label).classes("text-xs text-gray-500")
        ui.label(str(count)).classes(text_classes)