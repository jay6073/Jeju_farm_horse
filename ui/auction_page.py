"""
경매관리 화면.
- 탭1: 경매기록 등록 (마번 검증 + 최종낙찰 지정)
- 탭2: 전체 경매기록 목록 (마명/신청인/상태 JOIN 포함)
"""
from __future__ import annotations

from nicegui import run, ui

from services import auction_service
from services.auction_service import AuctionServiceError
from services.entrustment_service import a_horse_exists
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state


@ui.page("/auction")
def auction_page() -> None:
    content = render_nav("/auction")
    with content:
        ui.label("경매관리").classes("text-lg sm:text-xl font-medium")

        with ui.tabs().props("dense").classes("w-full border-b border-gray-200") as tabs:
            tab_register = ui.tab("경매기록 등록").classes("flex-1 text-xs sm:text-sm px-1")
            tab_list = ui.tab("전체 경매기록").classes("flex-1 text-xs sm:text-sm px-1")

        list_container_ref = {"container": None}

        with ui.tab_panels(tabs, value=tab_register).classes("w-full p-1 sm:p-4"):
            with ui.tab_panel(tab_register):
                _build_register_section(list_container_ref)
            with ui.tab_panel(tab_list):
                list_container_ref["container"] = _build_list_section()


def _build_register_section(list_container_ref: dict) -> None:
    with ui.column().classes("w-full max-w-2xl gap-3"):
        horse_id_input = ui.input(label="마번 (7자리)").classes("w-full")
        auction_name_input = ui.select(
            options=["낙찰", "유찰", "미상장"], label="경매 결과"
        ).classes("w-full")
        auction_date_input = ui.input(label="경매일").props("type=date").classes("w-full")
        price_input = ui.number(label="낙찰가 (선택)").classes("w-full")
        buyer_input = ui.input(label="매수인 (선택)").classes("w-full")
        is_final_checkbox = ui.checkbox("최종 낙찰 건으로 지정")

        def reset_form() -> None:
            horse_id_input.value = ""
            auction_name_input.value = None
            auction_date_input.value = ""  # None → ""
            price_input.value = None
            buyer_input.value = ""
            is_final_checkbox.value = False

        async def on_save() -> None:
            if not horse_id_input.value:
                ui.notify("마번은 필수입니다.", type="warning")
                return
            if not auction_name_input.value:
                ui.notify("경매 결과를 선택하세요.", type="warning")
                return

            exists = await run.io_bound(a_horse_exists, horse_id_input.value)
            if not exists:
                ui.notify(
                    f"마번 {horse_id_input.value}는 전체 말 관리(A)에 먼저 등록되어야 합니다.",
                    type="negative",
                )
                return

            try:
                await run.io_bound(
                    auction_service.add_auction_record,
                    horse_id_input.value,
                    auction_date_input.value or None,  # 여기 or None 추가
                    auction_name_input.value or None,
                    int(price_input.value) if price_input.value else None,
                    buyer_input.value or None,
                    is_final_checkbox.value,
                )
            except AuctionServiceError as e:
                ui.notify(str(e), type="negative")
                return

            ui.notify("경매기록 등록 완료", type="positive")
            reset_form()
            container = list_container_ref.get("container")
            if container is not None:
                await _refresh_list(container)

        ui.button("+ 등록", on_click=on_save).props("color=primary")


def _build_list_section():
    list_container = ui.column().classes("w-full")

    async def render_list() -> None:
        await _refresh_list(list_container)

    ui.timer(0.1, render_list, once=True)
    return list_container


async def _refresh_list(list_container) -> None:
    list_container.clear()
    records = await run.io_bound(auction_service.list_all_records)
    with list_container:
        if not records:
            empty_state("등록된 경매기록이 없습니다", icon="info")
            return
        with ui.card().classes(CARD_CLASSES + " p-4"):
            with ui.row().classes(
                "w-full text-xs text-gray-400 font-medium bg-gray-50 rounded-t-md "
                "px-2 py-1 -mt-4 -mx-4 mb-2"
            ):
                ui.label("마번").classes("w-24")
                ui.label("마명").classes("w-28")
                ui.label("경매명").classes("flex-1")
                ui.label("낙찰가").classes("w-28")
                ui.label("최종").classes("w-14")
                ui.label("").classes("w-20")  # 버튼 영역
            for r in records:
                with ui.row().classes(
                    "w-full items-center text-sm py-1.5 px-1 -mx-1 rounded "
                    "border-b border-gray-100 hover:bg-gray-50"
                ):
                    ui.label(r.get("horse_id", "-")).classes("w-24 text-gray-500")
                    ui.label(r.get("horse_name") or "-").classes("w-28")
                    ui.label(r.get("auction_name") or "-").classes("flex-1")
                    price = r.get("hammer_price")
                    ui.label(f"{price:,}" if price else "-").classes("w-28")
                    ui.label("✓" if r.get("is_final") else "").classes(
                        "w-14 text-primary"
                    )
                    with ui.row().classes("w-20 gap-1"):
                        ui.button(icon="edit", on_click=lambda e, rec=r: _open_edit_dialog(rec, list_container)).props(
                            "flat dense round size=sm"
                        )
                        ui.button(icon="delete", on_click=lambda e, rec=r: _confirm_delete(rec, list_container)).props(
                            "flat dense round size=sm color=negative"
                        )


def _open_edit_dialog(record: dict, list_container) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(f"경매기록 수정 (마번 {record['horse_id']})").classes("text-sm font-medium")
        name_input = ui.select(
            options=["낙찰", "유찰", "미상장"],
            value=record.get("auction_name") or None,
            label="경매 결과",
        ).classes("w-full")
        price_input = ui.number(label="낙찰가", value=record.get("hammer_price")).classes("w-full")
        buyer_input = ui.input(label="매수인", value=record.get("buyer_name") or "").classes("w-full")
        is_final_checkbox = ui.checkbox("최종 낙찰 건으로 지정", value=bool(record.get("is_final")))

        async def on_confirm() -> None:
            fields = {
                "auction_name": name_input.value or None,
                "hammer_price": int(price_input.value) if price_input.value else None,
                "buyer_name": buyer_input.value or None,
                "is_final": is_final_checkbox.value,
            }
            await run.io_bound(auction_service.update_auction_record, record["id"], fields)
            ui.notify("수정 완료", type="positive")
            dialog.close()
            await _refresh_list(list_container)

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("취소", on_click=dialog.close).props("flat")
            ui.button("저장", on_click=on_confirm).props("color=primary")
    dialog.open()


def _confirm_delete(record: dict, list_container) -> None:
    with ui.dialog() as dialog, ui.card():
        ui.label(f"마번 {record['horse_id']}의 경매기록을 삭제하시겠습니까?")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("취소", on_click=dialog.close).props("flat")

            async def on_confirm() -> None:
                dialog.close()
                await run.io_bound(auction_service.delete_auction_record, record["id"])
                ui.notify("삭제 완료", type="positive")
                await _refresh_list(list_container)

            ui.button("삭제", on_click=on_confirm).props("color=negative")
    dialog.open()