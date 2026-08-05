"""
통합조회 화면 (기능 단위로 단계적 구성).

단계:
  1. render_profile_detail — 상세 3카드 (위탁 / 경매 / 경주)  ✓
  2. 마번 조회 연결  ✓
  3. 신청인 목록  ✓
  4. 목록 → 상세 연결  ✓
  5. 검색 기준 전환으로 합치기  ✓
  6. nav / main 등록  ✓
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from nicegui import run, ui

from services import entrustment_dashboard_service, entrustment_service
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state, status_badge

_SEARCH_MODES = ["마번", "신청인"]


def _fmt_date(value: Any) -> str:
    if value is None:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    return text[:10] if text else "-"


def _fmt_fee(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_text(value: Any) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text if text else "-"


def _kv_row(label: str, value: str) -> None:
    with ui.row().classes(
        "w-full justify-between text-sm py-1 border-b border-gray-100"
    ):
        ui.label(label).classes("text-gray-500")
        ui.label(value)


def render_profile_detail(container, profile: dict[str, Any]) -> None:
    """
    말 1두 통합 상세(위탁 정보 / 경매 이력 / 경주성적)를 container에 그린다.
    profile은 get_horse_full_profile() 반환값과 동일한 구조:
      { horse, auctions, race_records, career_summary }
    """
    container.clear()
    horse = profile["horse"]
    auctions = profile.get("auctions") or []
    race_records = profile.get("race_records") or []
    career = profile.get("career_summary")

    with container:
        # ── 1) 위탁 정보 ─────────────────────────────────────────────
        with ui.card().classes(CARD_CLASSES + " p-4"):
            with ui.row().classes("w-full items-center gap-2 mb-2"):
                ui.label("위탁 정보").classes("text-sm font-medium")
                status_badge(horse.status)

            with ui.row().classes("w-full gap-8 flex-wrap"):
                with ui.column().classes("flex-1 min-w-[240px] gap-0"):
                    _kv_row("마번", _fmt_text(horse.horse_id))
                    _kv_row("마명", _fmt_text(horse.name))
                    _kv_row("부마명", _fmt_text(horse.sire_name))
                    _kv_row("성별", _fmt_text(horse.sex))
                    _kv_row("출생일", _fmt_date(horse.birth_date))
                    _kv_row("사업연도", _fmt_text(horse.application_year))
                with ui.column().classes("flex-1 min-w-[240px] gap-0"):
                    _kv_row("신청인", _fmt_text(horse.applicant_name))
                    _kv_row("목장명", _fmt_text(horse.farm_name))
                    _kv_row("입사일", _fmt_date(horse.farm_in_date))
                    _kv_row("퇴사일", _fmt_date(horse.farm_out_date))
                    _kv_row("위탁비", _fmt_fee(horse.entrustment_fee))
                    _kv_row("최초경매결과", _fmt_text(horse.first_result))
                    _kv_row("최종경매결과", _fmt_text(horse.final_result))

        # ── 2) 경매 이력 ─────────────────────────────────────────────
        with ui.card().classes(CARD_CLASSES + " p-4"):
            ui.label("경매 이력").classes("text-sm font-medium mb-2")
            if not auctions:
                empty_state("경매 이력이 없습니다", icon="gavel")
            else:
                with ui.column().classes("w-full overflow-x-auto"):
                    with ui.row().classes(
                        "w-full flex-nowrap text-xs text-gray-400 font-medium "
                        "bg-gray-50 rounded-t-md px-2 py-1"
                    ).props("no-wrap"):
                        ui.label("상장일").classes("w-28 shrink-0")
                        ui.label("결과").classes("w-28 shrink-0")
                        ui.label("낙찰가").classes("w-28 shrink-0 text-right")
                        ui.label("구매자").classes("w-32 shrink-0")
                        ui.label("최종").classes("w-16 shrink-0")
                    for a in auctions:
                        with ui.row().classes(
                            "w-full flex-nowrap items-center text-sm py-1.5 px-1 "
                            "border-b border-gray-100"
                        ).props("no-wrap"):
                            ui.label(_fmt_date(a.auction_date)).classes("w-28 shrink-0")
                            ui.label(_fmt_text(a.auction_name)).classes("w-28 shrink-0")
                            ui.label(_fmt_fee(a.hammer_price)).classes(
                                "w-28 shrink-0 text-right"
                            )
                            ui.label(_fmt_text(a.buyer_name)).classes("w-32 shrink-0")
                            ui.label("Y" if a.is_final else "-").classes("w-16 shrink-0")

        # ── 3) 경주성적 ──────────────────────────────────────────────
        with ui.card().classes(CARD_CLASSES + " p-4"):
            ui.label("경주성적").classes("text-sm font-medium mb-2")
            if career:
                with ui.row().classes("w-full gap-3 flex-wrap mb-3"):
                    ui.label(f"출주 {career.get('total_starts') or 0}").classes(
                        "text-sm px-3 py-1 bg-gray-50 rounded-md"
                    )
                    ui.label(f"1위 {career.get('total_wins') or 0}").classes(
                        "text-sm px-3 py-1 bg-gray-50 rounded-md"
                    )
                    ui.label(f"승률 {career.get('win_rate') or 0}%").classes(
                        "text-sm px-3 py-1 bg-gray-50 rounded-md"
                    )
                    prize = career.get("total_prize_money") or 0
                    ui.label(f"총상금 {prize:,}").classes(
                        "text-sm px-3 py-1 bg-gray-50 rounded-md"
                    )
            if not race_records:
                empty_state("경주 기록이 없습니다", icon="flag")
            else:
                with ui.column().classes("w-full overflow-x-auto"):
                    with ui.row().classes(
                        "w-full flex-nowrap text-xs text-gray-400 font-medium "
                        "bg-gray-50 rounded-t-md px-2 py-1"
                    ).props("no-wrap"):
                        ui.label("경주일자").classes("w-28 shrink-0")
                        ui.label("경주명").classes("w-40 shrink-0")
                        ui.label("거리").classes("w-20 shrink-0")
                        ui.label("순위").classes("w-16 shrink-0")
                        ui.label("기수").classes("w-24 shrink-0")
                        ui.label("기록").classes("w-24 shrink-0")
                    for r in race_records:
                        with ui.row().classes(
                            "w-full flex-nowrap items-center text-sm py-1.5 px-1 "
                            "border-b border-gray-100"
                        ).props("no-wrap"):
                            ui.label(_fmt_date(r.get("race_date"))).classes(
                                "w-28 shrink-0"
                            )
                            ui.label(_fmt_text(r.get("race_name"))).classes(
                                "w-40 shrink-0 truncate"
                            )
                            dist = r.get("distance")
                            ui.label("-" if dist is None else f"{dist}").classes(
                                "w-20 shrink-0"
                            )
                            ui.label(_fmt_text(r.get("rank"))).classes("w-16 shrink-0")
                            ui.label(_fmt_text(r.get("jockey"))).classes("w-24 shrink-0")
                            ui.label(_fmt_text(r.get("record_time"))).classes(
                                "w-24 shrink-0"
                            )


def render_applicant_horse_list(
    container,
    horses: list,
    applicant_query: str,
    on_select: Optional[Callable] = None,
) -> None:
    """
    신청인 검색 결과 목록을 표시한다.
    on_select(horse_id)가 있으면 각 행에 「상세」 버튼으로 연결한다.
    """
    container.clear()
    with container:
        ui.label(
            f"신청인「{applicant_query}」  {len(horses)}두"
        ).classes("text-sm text-gray-500 mb-1")

        if not horses:
            empty_state("해당 신청인의 위수탁마가 없습니다", icon="info")
            return

        with ui.card().classes(CARD_CLASSES + " p-4 overflow-x-auto"):
            with ui.column().classes("min-w-[780px]"):
                with ui.row().classes(
                    "w-full flex-nowrap text-xs text-gray-400 font-medium "
                    "bg-gray-50 rounded-t-md px-2 py-1 -mt-4 -mx-4 mb-2"
                ).props("no-wrap"):
                    ui.label("마번").classes("w-24 shrink-0")
                    ui.label("마명").classes("w-32 shrink-0")
                    ui.label("사업연도").classes("w-20 shrink-0")
                    ui.label("목장명").classes("w-36 shrink-0")
                    ui.label("상태").classes("w-24 shrink-0")
                    ui.label("위탁비").classes("w-28 shrink-0 text-right")
                    ui.label("").classes("w-16 shrink-0")

                for h in horses:
                    with ui.row().classes(
                        "w-full flex-nowrap items-center text-sm py-1.5 px-1 "
                        "-mx-1 rounded border-b border-gray-100 hover:bg-gray-50"
                    ).props("no-wrap"):
                        ui.label(h.horse_id or "-").classes("w-24 shrink-0 text-gray-500")
                        ui.label(h.name or "-").classes("w-32 shrink-0 truncate")
                        ui.label(_fmt_text(h.application_year)).classes("w-20 shrink-0")
                        ui.label(h.farm_name or "-").classes("w-36 shrink-0 truncate")
                        ui.label(h.status or "-").classes("w-24 shrink-0")
                        ui.label(_fmt_fee(h.entrustment_fee)).classes(
                            "w-28 shrink-0 text-right"
                        )
                        if on_select:
                            ui.button(
                                "상세",
                                on_click=lambda e, hid=h.horse_id: on_select(hid),
                            ).props("flat dense size=sm color=primary").classes(
                                "w-16 shrink-0"
                            )


@ui.page("/profile")
def profile_page() -> None:
    """검색 기준(마번/신청인) 하나로 조회하고, 상세 3카드를 표시한다."""
    content = render_nav("/profile")
    with content:
        ui.label("통합조회").classes("text-lg sm:text-xl font-medium")

        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
            mode_select = ui.select(
                options=_SEARCH_MODES, value="마번", label="검색 기준"
            ).classes("w-36")
            query_input = ui.input(label="마번 (7자리)").classes("w-56")

            def sync_query_label(_=None) -> None:
                label = "신청인" if mode_select.value == "신청인" else "마번 (7자리)"
                query_input._props["label"] = label
                query_input.value = None
                query_input.update()

            mode_select.on_value_change(sync_query_label)

            async def load_detail(horse_id: str) -> None:
                profile = await run.io_bound(
                    entrustment_dashboard_service.get_horse_full_profile, horse_id
                )
                if profile is None:
                    detail_container.clear()
                    with detail_container:
                        empty_state(
                            f"마번 {horse_id}에 해당하는 위탁 계약이 없습니다",
                            icon="info",
                        )
                    return
                render_profile_detail(detail_container, profile)

            async def on_search() -> None:
                detail_container.clear()
                list_container.clear()
                query = (query_input.value or "").strip()
                mode = mode_select.value

                if mode == "신청인":
                    if not query:
                        ui.notify("신청인을 입력하세요.", type="warning")
                        with list_container:
                            empty_state("신청인을 입력한 뒤 조회하세요", icon="search")
                        return

                    horses = await run.io_bound(
                        entrustment_service.list_horses, None, query, None
                    )
                    horses = sorted(horses, key=lambda h: h.name or "")
                    render_applicant_horse_list(
                        list_container,
                        horses,
                        query,
                        on_select=load_detail,
                    )
                    with detail_container:
                        empty_state(
                            "목록에서 「상세」를 누르면 아래에 표시됩니다",
                            icon="info",
                        )
                    return

                if not query:
                    ui.notify("마번을 입력하세요.", type="warning")
                    with detail_container:
                        empty_state("마번을 입력한 뒤 조회하세요", icon="search")
                    return
                await load_detail(query)

            ui.button("조회", on_click=on_search).props("color=primary")

        query_input.on("keydown.enter", on_search)

        list_container = ui.column().classes("w-full")
        detail_container = ui.column().classes("w-full gap-3")
        with detail_container:
            empty_state("검색 기준을 고른 뒤 조회하세요", icon="search")
