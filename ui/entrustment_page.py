"""
위탁관리 화면.
- 탭1: 개별 위탁 계약 등록 (A의 horses에 존재하는 마번인지 검증)
- 탭2: 위탁 계약 목록 (상태별 필터, 상태 변경)
- 탭3: 엑셀 일괄 등록 (미리보기 -> 확정)
"""
from __future__ import annotations

from nicegui import events, run, ui

from config.constants import HORSE_STATUS_OPTIONS
from services import entrustment_service, entrustment_import_service
from services.entrustment_service import EntrustmentServiceError, a_horse_exists
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state


@ui.page("/entrustment")
def entrustment_page() -> None:
    content = render_nav("/entrustment")
    with content:
        ui.label("위탁관리").classes("text-lg sm:text-xl font-medium")

        with ui.tabs().props("dense").classes("w-full border-b border-gray-200") as tabs:
            tab_register = ui.tab("위탁 계약 등록").classes("flex-1 text-xs sm:text-sm px-1")
            tab_list = ui.tab("위탁 계약 목록").classes("flex-1 text-xs sm:text-sm px-1")
            tab_import = ui.tab("엑셀 일괄 등록").classes("flex-1 text-xs sm:text-sm px-1")

        with ui.tab_panels(tabs, value=tab_register).classes("w-full p-1 sm:p-4"):
            with ui.tab_panel(tab_register):
                _build_register_section()
            with ui.tab_panel(tab_list):
                _build_list_section()
            with ui.tab_panel(tab_import):
                _build_import_section()


def _build_register_section() -> None:
    with ui.column().classes("w-full max-w-2xl gap-3"):
        horse_id_input = ui.input(label="마번 (7자리)").classes("w-full")
        name_input = ui.input(label="마명").classes("w-full")   # 추가
        applicant_input = ui.input(label="신청인").classes("w-full")
        farm_name_input = ui.input(label="목장명").classes("w-full")
        farm_in_input = ui.input(label="입사일").props("type=date").classes("w-full")
        farm_out_input = ui.input(label="퇴사일 (선택)").props("type=date").classes("w-full")
        fee_input = ui.number(label="위탁비 (부가세포함)").classes("w-full")
        year_input = ui.number(label="사업연도").classes("w-full")

        def reset_form() -> None:
            horse_id_input.value = ""
            name_input.value = ""   # 추가
            applicant_input.value = ""
            farm_name_input.value = ""
            farm_in_input.value = ""
            farm_out_input.value = ""
            fee_input.value = None
            year_input.value = None

        async def on_save() -> None:
            if not horse_id_input.value:
                ui.notify("마번은 필수입니다.", type="warning")
                return
            if not name_input.value:                          # 추가
                ui.notify("마명은 필수입니다.", type="warning")
                return

            raw = {
                "horse_id": horse_id_input.value,
                "horse_name": name_input.value,                # 추가
                "applicant_name": applicant_input.value or None,
                "farm_name": farm_name_input.value or None,
                "farm_in_date": farm_in_input.value or None,
                "farm_out_date": farm_out_input.value or None,
                "entrustment_fee": int(fee_input.value) if fee_input.value else None,
                "application_year": int(year_input.value) if year_input.value else None,
            }

            try:
                horse = await run.io_bound(entrustment_service.register_horse, raw)
            except EntrustmentServiceError as e:
                ui.notify(str(e), type="negative")
                return

            ui.notify(f"마번 {horse.horse_id} 위탁 계약 등록 완료", type="positive")
            reset_form()

        ui.button("+ 등록", on_click=on_save).props("color=primary")


def _build_list_section() -> None:
    with ui.column().classes("w-full max-w-2xl gap-3"):
        status_select = ui.select(options=HORSE_STATUS_OPTIONS, label="상태").classes(
            "w-full max-w-xs"
        )
        list_container = ui.column().classes("w-full")

        async def render_list() -> None:
            list_container.clear()
            status = status_select.value
            horses = await run.io_bound(entrustment_service.list_horses, status)
            horses = sorted(horses, key=lambda h: h.name or "")  # 마명순 정렬
            with list_container:
                if not horses:
                    empty_state("조건에 맞는 위탁 계약이 없습니다", icon="info")
                    return
                with ui.card().classes(CARD_CLASSES + " p-4"):
                    with ui.row().classes(
                        "w-full text-xs text-gray-400 font-medium bg-gray-50 rounded-t-md "
                        "px-2 py-1 -mt-4 -mx-4 mb-2"
                    ):
                        ui.label("마번").classes("w-28")
                        ui.label("마명").classes("flex-1")
                        ui.label("신청인").classes("w-32")
                        ui.label("상태").classes("w-24")
                        ui.label("").classes("w-20")
                    for h in horses:
                        with ui.row().classes(
                            "w-full items-center text-sm py-1.5 px-1 -mx-1 rounded "
                            "border-b border-gray-100 hover:bg-gray-50"
                        ):
                            ui.label(h.horse_id).classes("w-28 text-gray-500")
                            ui.label(h.name or "-").classes("flex-1")
                            ui.label(h.applicant_name or "-").classes("w-32")
                            ui.label(h.status).classes("w-24")
                            with ui.row().classes("w-20 gap-1"):
                                ui.button(
                                    icon="edit",
                                    on_click=lambda e, horse=h: _open_edit_dialog(horse, render_list),
                                ).props("flat dense round size=sm")
                                ui.button(
                                    icon="delete",
                                    on_click=lambda e, horse=h: _confirm_delete(horse, render_list),
                                ).props("flat dense round size=sm color=negative")

        status_select.on_value_change(render_list)
        render_list()


def _open_edit_dialog(horse, on_done) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(f"위탁 계약 수정 (마번 {horse.horse_id})").classes("text-sm font-medium")
        applicant_input = ui.input(label="신청인", value=horse.applicant_name or "").classes("w-full")
        farm_name_input = ui.input(label="목장명", value=horse.farm_name or "").classes("w-full")
        farm_out_input = ui.input(
            label="퇴사일",
            value=str(horse.farm_out_date) if horse.farm_out_date else "",
        ).props("type=date").classes("w-full")
        fee_input = ui.number(label="위탁비", value=horse.entrustment_fee).classes("w-full")
        status_edit_select = ui.select(
            options=HORSE_STATUS_OPTIONS, value=horse.status, label="상태"
        ).classes("w-full")

        async def on_confirm() -> None:
            fields = {
                "applicant_name": applicant_input.value or None,
                "farm_name": farm_name_input.value or None,
                "farm_out_date": farm_out_input.value or None,
                "entrustment_fee": int(fee_input.value) if fee_input.value else None,
                "status": status_edit_select.value,
            }
            try:
                await run.io_bound(
                    entrustment_service.update_horse_fields, horse.horse_id, fields
                )
            except EntrustmentServiceError as e:
                ui.notify(str(e), type="negative")
                return
            ui.notify("수정 완료", type="positive")
            dialog.close()
            await on_done()

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("취소", on_click=dialog.close).props("flat")
            ui.button("저장", on_click=on_confirm).props("color=primary")
    dialog.open()


def _confirm_delete(horse, on_done) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("warning").classes("text-red-500 text-xl")
            ui.label("위탁 계약 삭제").classes("text-base font-medium")
        ui.label(f"마번 {horse.horse_id}({horse.name or '-'})의 위탁 계약을 삭제합니다.").classes(
            "text-sm mt-2"
        )
        ui.label(
            "⚠️ 연관된 경매기록, 경주기록, 통산요약이 모두 함께 삭제되며 "
            "이 작업은 되돌릴 수 없습니다."
        ).classes("text-xs text-red-600 mt-1")
        ui.label(
            "정상적으로 위탁이 종료된 경우라면 삭제 대신 상태를 '위탁종료'로 변경하세요."
        ).classes("text-xs text-gray-400 mt-1")
        with ui.row().classes("w-full justify-end gap-2 mt-3"):
            ui.button("취소", on_click=dialog.close).props("flat")

            async def on_confirm() -> None:
                dialog.close()
                try:
                    await run.io_bound(entrustment_service.delete_horse, horse.horse_id)
                except EntrustmentServiceError as e:
                    ui.notify(str(e), type="negative")
                    return
                ui.notify("위탁 계약 및 연관 기록 삭제 완료", type="positive")
                await on_done()

            ui.button("정말 삭제", on_click=on_confirm).props("color=negative")
    dialog.open()


def _build_import_section() -> None:
    with ui.column().classes("w-full max-w-2xl gap-3"):
        ui.label(
            "필수 컬럼: 마명, 마종, 마번, 신청인 등 위탁 계약 관련 컬럼. "
            "마번이 전체 말 관리(A)에 등록되어 있어야 위탁 계약이 저장됩니다."
        ).classes("text-xs text-gray-400 break-words w-full")

        overwrite_checkbox = ui.checkbox(
            "이미 존재하는 위탁 계약/경매기록 덮어쓰기 (재이관 시 체크)"
        )

        preview_container = ui.column().classes("w-full")
        commit_container = ui.column().classes("w-full")

        async def on_upload(e: events.UploadEventArguments) -> None:
            preview_container.clear()
            commit_container.clear()

            try:
                if hasattr(e, "content") and e.content:
                    file_bytes = e.content
                elif hasattr(e, "file"):
                    file_bytes = await e.file.read()
                else:
                    raise Exception("파일 데이터를 읽을 수 없습니다.")

                df, missing_cols = await run.io_bound(
                    entrustment_import_service.preview_excel, file_bytes
                )
            except Exception as ex:
                with preview_container:
                    with ui.row().classes(
                        "items-center gap-2 py-3 px-4 bg-red-50 rounded-lg w-full"
                    ):
                        ui.icon("warning").classes("text-red-500")
                        ui.label(f"엑셀 파일 읽기 실패: {str(ex)}").classes(
                            "text-red-600 text-sm"
                        )
                return

            if missing_cols:
                with preview_container:
                    with ui.row().classes(
                        "items-center gap-2 py-3 px-4 bg-red-50 rounded-lg w-full"
                    ):
                        ui.icon("error").classes("text-red-500")
                        ui.label(f"필수 컬럼 누락: {', '.join(missing_cols)}").classes(
                            "text-red-600 text-sm"
                        )
                return

            with preview_container:
                with ui.card().classes(CARD_CLASSES + " p-4 w-full"):
                    ui.label(f"{len(df)}행 확인됨 (전체 말 관리 등록 여부는 실제 등록 시 확인됩니다)").classes(
                        "text-sm text-gray-500"
                    )

            async def on_commit() -> None:
                result = await run.io_bound(
                    entrustment_import_service.import_horses_from_excel,
                    file_bytes,
                    overwrite_checkbox.value,
                )

                has_issues = bool(getattr(result, "skip_details", None)) or bool(
                    getattr(result, "warnings", None)
                )

                ui.notify(
                    f"성공 {result.success_count}건, 덮어씀 {result.overwritten_count}건, "
                    f"스킵 {result.skipped_count}건"
                    + (" — 확인이 필요한 항목이 있습니다" if has_issues else ""),
                    type="warning" if has_issues else "positive",
                )

                if has_issues:
                    with preview_container:
                        with ui.row().classes(
                                "items-center justify-between gap-2 py-2 px-4 "
                                "bg-orange-50 rounded-lg w-full mt-2"
                        ):
                            ui.label(
                                f"스킵 {result.skipped_count}건"
                                + (
                                    f", 경고 {len(result.warnings)}건"
                                    if getattr(result, "warnings", None)
                                    else ""
                                )
                            ).classes("text-sm text-orange-700")
                            ui.button(
                                "자세히 보기",
                                on_click=lambda: _open_import_detail_dialog(result),
                            ).props("flat dense color=orange")

                commit_container.clear()

            with commit_container:
                ui.button("일괄 등록", on_click=on_commit).props("color=primary")

        ui.upload(on_upload=on_upload, auto_upload=True).props(
            "flat bordered color=primary accept=.xlsx,.xls,.xlsm dense"
        ).classes(
            "w-full max-w-full rounded-xl border-2 border-dashed border-gray-300 "
            "bg-gray-50/50 hover:border-blue-400 transition-colors"
        )

def _open_import_detail_dialog(result) -> None:
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
        ui.label("일괄 등록 상세 내역").classes("text-base font-medium")

        skip_details = getattr(result, "skip_details", None) or []
        warnings = getattr(result, "warnings", None) or []

        with ui.scroll_area().classes("w-full max-h-96"):
            if skip_details:
                ui.label(f"스킵된 항목 ({len(skip_details)}건)").classes(
                    "text-sm font-medium text-orange-600 mt-2"
                )
                for detail in skip_details:
                    ui.label(f"• {detail}").classes("text-xs text-orange-600 ml-2")

            if warnings:
                ui.label(f"경고 ({len(warnings)}건)").classes(
                    "text-sm font-medium text-amber-600 mt-3"
                )
                for w in warnings:
                    ui.label(f"• {w}").classes("text-xs text-amber-600 ml-2")

            if not skip_details and not warnings:
                ui.label("표시할 상세 내역이 없습니다.").classes(
                    "text-xs text-gray-400"
                )

        with ui.row().classes("w-full justify-end mt-3"):
            ui.button("닫기", on_click=dialog.close).props("flat")
    dialog.open()