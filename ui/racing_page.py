"""
경주성적 화면.
- 상단: "경주기록 확인" 버튼 (위탁종료+미확인 대상 전체 스크래핑 트리거)
- 마번 조회: 특정 말의 경주기록(마명 포함)과 통산요약 조회
"""
from __future__ import annotations

from nicegui import run, ui

from services import racing_service
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state


@ui.page("/racing")
def racing_page() -> None:
    content = render_nav("/racing")
    with content:
        ui.label("경주성적").classes("text-lg sm:text-xl font-medium")

        with ui.row().classes("w-full items-center gap-3"):
            refresh_button = ui.button("경주기록 확인 (전체)", icon="refresh").props(
                "color=primary"
            )
            progress_label = ui.label("").classes("text-sm text-gray-500")

        result_container = ui.column().classes("w-full")

        async def on_refresh() -> None:
            refresh_button.disable()
            result_container.clear()

            def on_progress(current: int, total: int, horse_id: str) -> None:
                progress_label.set_text(f"{current}/{total} 처리 중 (마번 {horse_id})")

            result = await run.io_bound(
                racing_service.refresh_all_racehorses, progress_callback=on_progress
            )
            progress_label.set_text("")
            refresh_button.enable()

            with result_container:
                with ui.card().classes(CARD_CLASSES + " p-4"):
                    ui.label(
                        f"대상 {result.total_targets}건 · 성공 {result.success_count}건 · "
                        f"경주이력없음 {result.no_race_history_count}건 · 실패 {result.failed_count}건"
                    ).classes("text-sm")
                    if result.failed_details:
                        ui.label("실패 상세").classes("text-xs font-medium text-gray-600 mt-2")
                        for detail in result.failed_details:
                            ui.label(detail).classes("text-xs text-red-600")

        refresh_button.on_click(on_refresh)

        ui.separator()

        ui.label("마번으로 경주기록 조회").classes("text-sm text-gray-500")
        with ui.row().classes("w-full gap-3 max-w-xl"):
            horse_id_input = ui.input(label="마번 (7자리)").classes("flex-1")
            search_button = ui.button("조회", icon="search").props("outline color=primary")

        detail_container = ui.column().classes("w-full")

        async def on_search() -> None:
            detail_container.clear()
            horse_id = horse_id_input.value
            if not horse_id:
                ui.notify("마번을 입력하세요.", type="warning")
                return

            records = await run.io_bound(
                racing_service.get_race_records_with_horse_name, horse_id
            )
            summary = await run.io_bound(racing_service.get_career_summary, horse_id)

            with detail_container:
                if summary:
                    with ui.card().classes(CARD_CLASSES + " p-4 mb-3"):
                        ui.label(f"{summary.get('total_starts', 0)}전 "
                                 f"{summary.get('total_wins', 0)}승 · "
                                 f"승률 {summary.get('win_rate', 0)}% · "
                                 f"총상금 {summary.get('total_prize_money', 0):,}원").classes(
                            "text-sm font-medium"
                        )
                        rating = summary.get("rating")
                        if rating:
                            ui.label(f"레이팅: {rating}").classes("text-xs text-gray-500")

                if not records:
                    empty_state("경주기록이 없습니다", icon="flag")
                    return

                with ui.card().classes(CARD_CLASSES + " p-4"):
                    with ui.row().classes(
                        "w-full text-xs text-gray-400 font-medium bg-gray-50 rounded-t-md "
                        "px-2 py-1 -mt-4 -mx-4 mb-2"
                    ):
                        ui.label("경주일").classes("w-24")
                        ui.label("경주명").classes("flex-1")
                        ui.label("순위").classes("w-16")
                        ui.label("기수").classes("w-20")
                        ui.label("기록").classes("w-20")
                    for r in records:
                        with ui.row().classes(
                            "w-full items-center text-sm py-1.5 px-1 -mx-1 rounded "
                            "border-b border-gray-100 hover:bg-gray-50"
                        ):
                            ui.label(str(r.get("race_date") or "-")).classes("w-24 text-gray-500")
                            ui.label(r.get("race_name") or "-").classes("flex-1")
                            ui.label(r.get("rank") or "-").classes("w-16")
                            ui.label(r.get("jockey") or "-").classes("w-20")
                            ui.label(r.get("record_time") or "-").classes("w-20")

        search_button.on_click(on_search)
        horse_id_input.on("keydown.enter", on_search)