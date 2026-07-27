"""
대시보드 화면 (아키텍처 프롬프트 4-3절).

- 오늘 기준(상태='정상') 마종별 두수 카드 5개 + 합계 카드
- 카드 클릭 시 해당 마종으로 목록 필터링 (다시 클릭하면 필터 해제)
- 카드 아래 전체 보유마 목록: 마번 / 마명 / 마종 / 상태(+상태발생일자)
- 마명 검색창, 마명은 ui.link로 렌더링해 /main?horse_id=로 딥링크
- [통합 시 추가] 위탁 통계 섹션 (entrustment_dashboard_service.overview_kpis)
"""
from __future__ import annotations

from nicegui import run, ui

from models.horse import HORSE_SPECIES
from repository.horse_repository import HorseRepository
from services import dashboard_service, entrustment_dashboard_service
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state, status_badge

_repo = HorseRepository()


@ui.page("/dashboard", response_timeout=30)
async def dashboard_page() -> None:
    content = render_nav("/dashboard")
    with content:
        ui.label("보유두수 대시보드").classes("text-xl font-medium")

        counts = await run.io_bound(dashboard_service.get_species_counts, _repo)
        total = sum(counts.values())

        selected_species = {"value": None}

        with ui.row().classes("w-full gap-3 flex-wrap") as card_row:
            pass

        ui.separator()

        with ui.row().classes("w-full gap-3 flex-wrap") as entrustment_row:
            pass

        ui.separator()

        search_input = ui.input(label="마명 검색").classes("w-full max-w-xs")
        list_container = ui.column().classes("w-full")

        all_horses = await run.io_bound(dashboard_service.get_all_horses, _repo)
        kpis = await run.io_bound(entrustment_dashboard_service.overview_kpis)

        def render_species_cards() -> None:
            card_row.clear()
            with card_row:
                _render_count_card(
                    "합계", total, highlight=selected_species["value"] is None,
                    on_click=lambda: select_species(None),
                )
                for species in HORSE_SPECIES:
                    _render_count_card(
                        species,
                        counts.get(species, 0),
                        highlight=selected_species["value"] == species,
                        on_click=lambda s=species: select_species(s),
                    )

        def render_entrustment_cards() -> None:
            entrustment_row.clear()
            with entrustment_row:
                _render_count_card("위탁중", kpis["status_counts"].get("위탁중", 0))
                _render_count_card("위탁종료", kpis["status_counts"].get("위탁종료", 0))
                _render_count_card("경주기록확인필요", kpis["unverified_race_count"])

        def select_species(species: str | None) -> None:
            selected_species["value"] = species
            render_species_cards()
            render_list(search_input.value)

        def render_list(filter_text: str = "") -> None:
            list_container.clear()
            filter_text = (filter_text or "").strip()
            species_filter = selected_species["value"]
            filtered = [
                h for h in all_horses
                if (not filter_text or filter_text in h.마명)
                and (species_filter is None or h.마종 == species_filter)
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

        render_species_cards()
        render_entrustment_cards()
        search_input.on_value_change(lambda e: render_list(e.value))
        render_list()


def _render_count_card(
    label: str, count: int, highlight: bool = False, on_click=None,
) -> None:
    box_classes = "rounded-lg p-4 gap-1 border cursor-pointer transition-colors"
    box_classes += (
        " bg-primary/10 border-primary/20"
        if highlight
        else " bg-gray-50 border-gray-200 hover:bg-gray-100"
    )
    text_classes = "text-2xl font-medium"
    if highlight:
        text_classes += " text-primary"
    card = ui.column().classes(box_classes).style("min-width: 90px;")
    if on_click:
        card.on("click", on_click)
    with card:
        ui.label(label).classes("text-xs text-gray-500")
        ui.label(str(count)).classes(text_classes)