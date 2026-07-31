"""
대시보드 화면.
- 마종별 두수 카드 (클릭 시 해당 마종으로 목록 필터링)
- 위탁 통계 카드 (위탁중/위탁종료/경주기록확인필요, 클릭 시 해당 조건으로 목록 필터링)
- 목록에서 위수탁마는 위탁중/위탁종료 뱃지로 구분 표시
"""
from __future__ import annotations

from nicegui import run, ui

from models.horse import HORSE_SPECIES
from repository.horse_repository import HorseRepository
from services import dashboard_service, entrustment_dashboard_service, entrustment_service
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state, status_badge

_repo = HorseRepository()

_ENTRUSTMENT_BADGE_STYLE = {
    "위탁중": "bg-blue-100 text-blue-700",
    "위탁종료": "bg-gray-200 text-gray-600",
}


@ui.page("/dashboard", response_timeout=60)
async def dashboard_page() -> None:
    content = render_nav("/dashboard")
    with content:
        ui.label("보유두수 대시보드").classes("text-xl font-medium")

        counts = await run.io_bound(dashboard_service.get_species_counts, _repo)
        total = sum(counts.values())

        all_horses = await run.io_bound(dashboard_service.get_all_horses, _repo)
        kpis = await run.io_bound(entrustment_dashboard_service.overview_kpis)

        entrustment_horses = await run.io_bound(entrustment_service.list_horses, None)
        entrustment_status_map = {h.horse_id: h.status for h in entrustment_horses}

        unverified_ids = set(
            await run.io_bound(entrustment_service.list_unverified_ended_horses)
        )

        # selected_filter: {"type": "species"|"entrustment"|None, "value": str|None}
        selected_filter = {"type": None, "value": None}

        with ui.row().classes("w-full gap-3 flex-wrap") as card_row:
            pass

        ui.separator()

        with ui.row().classes("w-full gap-3 flex-wrap") as entrustment_row:
            pass

        ui.separator()

        with ui.row().classes("w-full gap-3 flex-wrap") as race_stats_row:
            pass

        ui.separator()

        search_input = ui.input(label="마명 검색").classes("w-full max-w-xs")
        list_container = ui.column().classes("w-full")

        def render_species_cards() -> None:
            card_row.clear()
            with card_row:
                _render_count_card(
                    "합계", total,
                    highlight=selected_filter["type"] is None,
                    on_click=lambda: select_filter(None, None),
                )
                for species in HORSE_SPECIES:
                    _render_count_card(
                        species,
                        counts.get(species, 0),
                        highlight=selected_filter == {"type": "species", "value": species},
                        on_click=lambda s=species: select_filter("species", s),
                    )

        def render_entrustment_cards() -> None:
            entrustment_row.clear()
            with entrustment_row:
                _render_count_card(
                    "위탁중",
                    kpis["status_counts"].get("위탁중", 0),
                    highlight=selected_filter == {"type": "entrustment", "value": "위탁중"},
                    on_click=lambda: select_filter("entrustment", "위탁중"),
                )
                _render_count_card(
                    "위탁종료",
                    kpis["status_counts"].get("위탁종료", 0),
                    highlight=selected_filter == {"type": "entrustment", "value": "위탁종료"},
                    on_click=lambda: select_filter("entrustment", "위탁종료"),
                )
                _render_count_card(
                    "경주기록확인필요",
                    kpis["unverified_race_count"],
                    highlight=selected_filter == {"type": "entrustment", "value": "미확인"},
                    on_click=lambda: select_filter("entrustment", "미확인"),
                )

        def render_race_stat_cards() -> None:
            race_stats_row.clear()
            with race_stats_row:
                _render_stat_card("1위 두수 합계", f"{kpis['total_race_wins']}두")
                _render_stat_card("전체 상금 합계", f"{kpis['total_prize_money']:,}원")

        def select_filter(filter_type: str | None, value: str | None) -> None:
            selected_filter["type"] = filter_type
            selected_filter["value"] = value
            render_species_cards()
            render_entrustment_cards()
            render_race_stat_cards()
            render_list(search_input.value)

        def render_list(filter_text: str = "") -> None:
            list_container.clear()
            filter_text = (filter_text or "").strip()

            filtered = [h for h in all_horses if not filter_text or filter_text in h.마명]

            ftype, fvalue = selected_filter["type"], selected_filter["value"]
            if ftype == "species":
                filtered = [h for h in filtered if h.마종 == fvalue]
            elif ftype == "entrustment":
                if fvalue == "미확인":
                    filtered = [h for h in filtered if h.마번 in unverified_ids]
                else:
                    filtered = [
                        h for h in filtered
                        if entrustment_status_map.get(h.마번) == fvalue
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
                        ui.label("상태").classes("w-32")
                        ui.label("위탁상태").classes("w-20")
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
                            with ui.row().classes("w-32 items-center gap-2"):
                                status_badge(h.상태)
                                if h.상태 != "정상" and h.상태발생일자:
                                    ui.label(h.상태발생일자).classes(
                                        "text-xs text-gray-400"
                                    )
                            entrustment_status = entrustment_status_map.get(h.마번)
                            with ui.row().classes("w-20"):
                                if entrustment_status:
                                    style = _ENTRUSTMENT_BADGE_STYLE.get(
                                        entrustment_status, "bg-gray-200 text-gray-600"
                                    )
                                    ui.label(entrustment_status).classes(
                                        f"text-xs px-2 py-0.5 rounded-full {style} inline-block"
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

def _render_stat_card(label: str, value: str) -> None:
    """클릭 필터가 없는 순수 통계 카드 (경주성적 합계용)."""
    with ui.column().classes(
        "rounded-lg p-4 gap-1 border bg-amber-50 border-amber-200"
    ).style("min-width: 120px;"):
        ui.label(label).classes("text-xs text-gray-500")
        ui.label(value).classes("text-2xl font-medium text-amber-700")