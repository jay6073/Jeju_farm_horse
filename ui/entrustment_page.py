"""
위탁관리 화면.
- 탭1: 개별 위탁 계약 등록 (A의 horses에 존재하는 마번인지 검증)
- 탭2: 위탁 계약 목록 (상태별 필터, 상태 변경)
- 탭3: 명단 조회 (사업연도·상태·신청인·마번/마명 복합 필터 + 엑셀 다운로드)
- 탭4: 엑셀 일괄 등록 (미리보기 -> 확정)
- 탭5: 연간·전체 통계 (1단계: UI 골격 + 집계 스텁)
"""
from __future__ import annotations

from datetime import date

from nicegui import events, run, ui

from config.constants import HORSE_STATUS_OPTIONS
from services import annual_report_service, entrustment_service, entrustment_import_service
from services.annual_report_service import ReportPreview, ReportScope
from services.entrustment_service import EntrustmentServiceError, a_horse_exists
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state

_STATUS_FILTER_OPTIONS = ["전체", *HORSE_STATUS_OPTIONS]


@ui.page("/entrustment")
def entrustment_page() -> None:
    content = render_nav("/entrustment")
    with content:
        ui.label("위탁관리").classes("text-lg sm:text-xl font-medium no-print")

        with ui.tabs().props("dense").classes(
            "w-full border-b border-gray-200 no-print"
        ) as tabs:
            tab_register = ui.tab("위탁 계약 등록").classes(
                "flex-1 justify-center text-xs sm:text-sm"
            )
            tab_list = ui.tab("위탁 계약 목록").classes(
                "flex-1 justify-center text-xs sm:text-sm"
            )
            tab_year = ui.tab("명단 조회").classes(
                "flex-1 justify-center text-xs sm:text-sm"
            )
            tab_import = ui.tab("엑셀 일괄 등록").classes(
                "flex-1 justify-center text-xs sm:text-sm"
            )
            tab_report = ui.tab("연간 통계").classes(
                "flex-1 justify-center text-xs sm:text-sm"
            )

        with ui.tab_panels(tabs, value=tab_register).classes("w-full p-1 sm:p-4"):
            with ui.tab_panel(tab_register):
                _build_register_section()
            with ui.tab_panel(tab_list):
                _build_list_section()
            with ui.tab_panel(tab_year):
                _build_year_list_section()
            with ui.tab_panel(tab_import):
                _build_import_section()
            with ui.tab_panel(tab_report):
                _build_report_section()


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


def _format_year_list_date(value) -> str:
    if value is None:
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    return text[:10] if text else "-"


def _format_year_list_fee(value) -> str:
    if value is None:
        return "-"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _build_year_list_section() -> None:
    """명단 조회: 복합 필터로 조회하고 동일 조건으로 엑셀 다운로드."""
    with ui.column().classes("w-full gap-3"):
        ui.label(
            "사업연도·상태·신청인·마번/마명 조건을 조합해 조회할 수 있습니다. "
            "엑셀은 현재 필터와 동일한 결과가 내려갑니다."
        ).classes("text-sm text-gray-500")

        with ui.row().classes("w-full items-end gap-3 flex-wrap"):
            year_input = ui.number(label="사업연도").classes("w-36")
            status_select = ui.select(
                options=_STATUS_FILTER_OPTIONS, value="전체", label="상태"
            ).classes("w-36")
            applicant_input = ui.input(label="신청인").classes("w-44")
            keyword_input = ui.input(label="마번/마명").classes("w-44")

            def _read_filters() -> tuple:
                year = int(year_input.value) if year_input.value else None
                status = (
                    None
                    if not status_select.value or status_select.value == "전체"
                    else status_select.value
                )
                applicant = (applicant_input.value or "").strip() or None
                keyword = (keyword_input.value or "").strip() or None
                return year, status, applicant, keyword

            def _filter_summary(year, status, applicant, keyword) -> str:
                parts = []
                if year is not None:
                    parts.append(f"{year}년")
                if status:
                    parts.append(status)
                if applicant:
                    parts.append(f"신청인「{applicant}」")
                if keyword:
                    parts.append(f"검색「{keyword}」")
                return " · ".join(parts) if parts else "전체"

            async def render_year_list() -> None:
                list_container.clear()
                result_label.set_text("")
                year, status, applicant, keyword = _read_filters()
                if not any([year is not None, status, applicant, keyword]):
                    ui.notify("필터를 하나 이상 입력하세요.", type="warning")
                    with list_container:
                        empty_state("필터를 하나 이상 입력한 뒤 조회하세요", icon="info")
                    return

                horses = await run.io_bound(
                    entrustment_service.search_horses,
                    year,
                    status,
                    applicant,
                    keyword,
                )
                summary = _filter_summary(year, status, applicant, keyword)
                result_label.set_text(f"{summary}  {len(horses)}두")

                with list_container:
                    if not horses:
                        empty_state("조건에 맞는 위수탁마가 없습니다", icon="info")
                        return

                    with ui.card().classes(CARD_CLASSES + " p-4 overflow-x-auto"):
                        with ui.column().classes("min-w-[1100px]"):
                            with ui.row().classes(
                                "w-full flex-nowrap text-xs text-gray-400 font-medium "
                                "bg-gray-50 rounded-t-md px-2 py-1 -mt-4 -mx-4 mb-2"
                            ).props("no-wrap"):
                                ui.label("마번").classes("w-24 shrink-0")
                                ui.label("마명").classes("w-28 shrink-0")
                                ui.label("부마명").classes("w-28 shrink-0")
                                ui.label("성별").classes("w-12 shrink-0")
                                ui.label("출생일").classes("w-28 shrink-0")
                                ui.label("신청인").classes("w-28 shrink-0")
                                ui.label("목장명").classes("w-32 shrink-0")
                                ui.label("입사일").classes("w-28 shrink-0")
                                ui.label("퇴사일").classes("w-28 shrink-0")
                                ui.label("위탁비").classes("w-28 shrink-0 text-right")

                            for h in horses:
                                with ui.row().classes(
                                    "w-full flex-nowrap items-center text-sm py-1.5 px-1 "
                                    "-mx-1 rounded border-b border-gray-100 hover:bg-gray-50"
                                ).props("no-wrap"):
                                    ui.label(h.horse_id or "-").classes(
                                        "w-24 shrink-0 text-gray-500"
                                    )
                                    ui.label(h.name or "-").classes(
                                        "w-28 shrink-0 truncate"
                                    )
                                    ui.label(h.sire_name or "-").classes(
                                        "w-28 shrink-0 truncate"
                                    )
                                    ui.label(h.sex or "-").classes("w-12 shrink-0")
                                    ui.label(_format_year_list_date(h.birth_date)).classes(
                                        "w-28 shrink-0"
                                    )
                                    ui.label(h.applicant_name or "-").classes(
                                        "w-28 shrink-0 truncate"
                                    )
                                    ui.label(h.farm_name or "-").classes(
                                        "w-32 shrink-0 truncate"
                                    )
                                    ui.label(_format_year_list_date(h.farm_in_date)).classes(
                                        "w-28 shrink-0"
                                    )
                                    ui.label(_format_year_list_date(h.farm_out_date)).classes(
                                        "w-28 shrink-0"
                                    )
                                    ui.label(_format_year_list_fee(h.entrustment_fee)).classes(
                                        "w-28 shrink-0 text-right"
                                    )

            async def on_export() -> None:
                year, status, applicant, keyword = _read_filters()
                if not any([year is not None, status, applicant, keyword]):
                    ui.notify("필터를 하나 이상 입력하세요.", type="warning")
                    return

                summary = _filter_summary(year, status, applicant, keyword)
                sheet_title = summary.replace(" · ", "_")[:31]
                excel_bytes = await run.io_bound(
                    entrustment_service.export_filtered_list,
                    year,
                    status,
                    applicant,
                    keyword,
                    sheet_title,
                )
                filename_year = year if year is not None else "검색"
                ui.download(excel_bytes, filename=f"위수탁마_{filename_year}.xlsx")

            ui.button("조회", on_click=render_year_list).props("color=primary")
            ui.button("엑셀 다운로드", icon="download", on_click=on_export).props(
                "outline color=primary"
            )

        year_input.on("keydown.enter", render_year_list)
        applicant_input.on("keydown.enter", render_year_list)
        keyword_input.on("keydown.enter", render_year_list)

        result_label = ui.label("").classes("text-sm text-gray-500")
        list_container = ui.column().classes("w-full")
        with list_container:
            empty_state("필터를 하나 이상 입력한 뒤 조회하세요", icon="info")


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
                btn.props("loading disable")
                try:
                    try:
                        result = await run.io_bound(
                            entrustment_import_service.import_horses_from_excel,
                            file_bytes,
                            overwrite_checkbox.value,
                        )
                    except Exception as ex:
                        ui.notify(f"일괄 등록 실패: {ex}", type="negative")
                        return

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
                finally:
                    btn.props(remove="loading disable")

            with commit_container:
                btn = ui.button("일괄 등록", on_click=on_commit).props("color=primary")

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


_REPORT_PRINT_STYLE = """
@media print {
  @page {
    size: A4 portrait;
    margin: 10mm;
  }

  header, .q-drawer, .q-drawer__backdrop, .no-print {
    display: none !important;
  }

  html, body,
  .q-layout, .q-page-container, .q-page,
  .nicegui-content, .q-tab-panels, .q-tab-panel {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    max-width: none !important;
    left: 0 !important;
    overflow: visible !important;
  }
  .q-page-container {
    padding-left: 0 !important;
    margin-left: 0 !important;
  }

  .print-area {
    box-shadow: none !important;
    border: none !important;
    width: 100% !important;
    max-width: none !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  .max-w-5xl {
    max-width: none !important;
    width: 100% !important;
  }

  .print-area .q-table__top,
  .print-area .q-table__bottom {
    display: none !important;
  }
}
"""


def _build_report_section() -> None:
    """연간·전체 기간 통계 미리보기 (1단계: UI + 스텁 집계)."""
    ui.add_css(_REPORT_PRINT_STYLE)
    with ui.column().classes("w-full max-w-5xl gap-4"):
        ui.label(
            "집계 범위를 선택한 뒤 미리보기하거나 엑셀로 저장하세요. "
            "화면 그대로 받으려면 미리보기 후 인쇄에서 PDF로 저장하면 됩니다. "
            "금액은 원 단위(천 단위 콤마)입니다."
        ).classes("text-xs text-gray-400 no-print")

        with ui.card().classes(CARD_CLASSES + " p-4 gap-3 no-print"):
            ui.label("집계 조건").classes("text-sm font-medium text-gray-700")
            scope_toggle = ui.toggle(
                {"year": "사업연도별", "all": "전체 기간"},
                value="year",
            ).props("dense unelevated")

            with ui.row().classes("w-full gap-3 items-end flex-wrap"):
                year_input = ui.number(
                    label="사업연도",
                    value=date.today().year,
                    format="%.0f",
                ).classes("w-36")
                preview_btn = ui.button("미리보기", icon="preview").props(
                    "color=primary"
                )
                export_btn = ui.button(
                    "엑셀 다운로드", icon="download"
                ).props("outline color=primary")
                print_btn = ui.button("인쇄", icon="print").props(
                    "outline color=primary"
                )
                print_btn.disable()

            def _sync_year_visibility() -> None:
                year_input.set_visibility(scope_toggle.value == "year")

            scope_toggle.on_value_change(_sync_year_visibility)
            _sync_year_visibility()

        result = ui.column().classes("w-full gap-3 print-area")

        def render_idle(message: str) -> None:
            result.clear()
            print_btn.disable()
            with result:
                empty_state(message, icon="analytics")

        def render_preview(preview: ReportPreview) -> None:
            result.clear()
            scope_tag = (
                "전체 기간"
                if preview.scope == "all"
                else f"사업연도 {preview.application_year}"
            )
            layout_tag = (
                "경주 성과 중심"
                if preview.layout == "racing"
                else "위탁 상태 중심"
            )

            with result:
                # —— p.1 style: title + KPI ——
                with ui.card().classes(CARD_CLASSES + " p-5 gap-3"):
                    with ui.row().classes(
                        "w-full items-start justify-between gap-2 flex-wrap"
                    ):
                        ui.label("요약").classes(
                            "text-xs tracking-wide text-gray-400 uppercase"
                        )
                        if preview.is_stub:
                            ui.badge("예시 데이터").props(
                                "color=grey-7 outline"
                            )

                    ui.label("제주목장 · 위탁 통계 보고").classes(
                        "text-xs text-gray-500"
                    )
                    ui.label(preview.title).classes(
                        "text-xl font-medium text-gray-900"
                    )

                    with ui.row().classes("w-full gap-2 items-center flex-wrap"):
                        ui.label(f"모집단: {scope_tag}").classes(
                            "text-xs text-gray-500"
                        )
                        ui.label("·").classes("text-xs text-gray-300")
                        ui.label(layout_tag).classes("text-xs text-gray-500")
                        ui.label("·").classes("text-xs text-gray-300")
                        ui.label(preview.subtitle).classes("text-xs text-gray-400")

                    ui.separator().classes("my-1")

                    ui.label("주요 지표").classes("text-sm font-medium")
                    ui.label(
                        "단위: 두수=두, 금액=원(천 단위 콤마), 승률=%"
                    ).classes("text-xs text-gray-400 -mt-1")

                    with ui.grid(columns=4).classes("w-full gap-2"):
                        for kpi in preview.kpis:
                            with ui.column().classes(
                                "border border-gray-200 bg-gray-50/50 "
                                "rounded-sm p-3 gap-0.5"
                            ):
                                ui.label(kpi.value).classes(
                                    "text-xl font-medium text-gray-900 "
                                    "leading-none"
                                )
                                label = kpi.label
                                if kpi.unit:
                                    label = f"{kpi.label} ({kpi.unit})"
                                ui.label(label).classes(
                                    "text-xs text-gray-500 mt-1"
                                )

                    with ui.column().classes(
                        "w-full gap-1 pt-2 border-t border-gray-100"
                    ):
                        ui.label("집계 기준").classes(
                            "text-xs font-medium text-gray-600"
                        )
                        for note in preview.notes:
                            ui.label(f"· {note}").classes(
                                "text-xs text-gray-400 leading-snug"
                            )

                # —— applicant breakdown ——
                with ui.card().classes(CARD_CLASSES + " p-5 gap-2"):
                    section_title = (
                        "신청인별 경주 성과"
                        if preview.layout == "racing"
                        else "신청인별 위탁 집계"
                    )
                    ui.label(section_title).classes("text-sm font-medium")
                    if preview.layout == "racing":
                        ui.label(
                            "출전·1착·상금은 해당 연도 출주에 한정하지 않고 "
                            "작성 시점 통산 성적(career_summary) 합산 기준입니다."
                        ).classes("text-xs text-gray-400 mb-1")
                    else:
                        ui.label(
                            "두수·위탁중·종료·위탁비·낙찰 현황입니다."
                        ).classes("text-xs text-gray-400 mb-1")

                    if not preview.applicant_rows:
                        empty_state("신청인 집계가 없습니다", icon="info")
                    else:
                        columns = [
                            {
                                "name": h,
                                "label": h,
                                "field": h,
                                "align": "left" if i == 0 else "right",
                            }
                            for i, h in enumerate(preview.applicant_headers)
                        ]
                        rows = [r.cells for r in preview.applicant_rows]
                        ui.table(
                            columns=columns,
                            rows=rows,
                            row_key="신청인",
                        ).classes("w-full").props("flat dense wrap-cells")

                if preview.win_horse_rows:
                    with ui.card().classes(CARD_CLASSES + " p-5 gap-2"):
                        ui.label("1착 기록 말").classes("text-sm font-medium")
                        ui.label(
                            "1착 수 내림차순 · 통산 career_summary 기준"
                        ).classes("text-xs text-gray-400 mb-1")
                        columns = [
                            {
                                "name": "마명",
                                "label": "마명",
                                "field": "마명",
                                "align": "left",
                            },
                            {
                                "name": "신청인",
                                "label": "신청인",
                                "field": "신청인",
                                "align": "left",
                            },
                            {
                                "name": "출전(회)",
                                "label": "출전(회)",
                                "field": "출전(회)",
                                "align": "right",
                            },
                            {
                                "name": "1착(회)",
                                "label": "1착(회)",
                                "field": "1착(회)",
                                "align": "right",
                            },
                            {
                                "name": "상금(원)",
                                "label": "상금(원)",
                                "field": "상금(원)",
                                "align": "right",
                            },
                        ]
                        rows = [
                            {
                                "마명": h.name,
                                "신청인": h.applicant_name,
                                "출전(회)": h.starts,
                                "1착(회)": h.wins,
                                "상금(원)": h.prize_won,
                            }
                            for h in preview.win_horse_rows
                        ]
                        ui.table(
                            columns=columns,
                            rows=rows,
                            row_key="마명",
                        ).classes("w-full").props("flat dense")

        async def on_preview() -> None:
            scope: ReportScope = scope_toggle.value or "year"
            year: int | None = None
            if scope == "year":
                if year_input.value is None:
                    ui.notify("사업연도를 입력하세요.", type="warning")
                    return
                year = int(year_input.value)

            result.clear()
            print_btn.disable()
            with result:
                with ui.row().classes(
                    "w-full items-center gap-2 py-8 justify-center"
                ):
                    ui.spinner(size="lg")
                    ui.label("보고서를 구성하는 중...").classes(
                        "text-gray-500 text-sm"
                    )

            try:
                preview = await run.io_bound(
                    annual_report_service.build_report_preview,
                    scope,
                    year,
                )
            except ValueError as e:
                render_idle(str(e))
                ui.notify(str(e), type="negative")
                return

            render_preview(preview)
            print_btn.enable()
            if preview.is_stub:
                ui.notify(
                    "예시 수치입니다. 다음 단계에서 실제 DB 집계로 바뀝니다.",
                    type="info",
                )

        async def on_export() -> None:
            scope: ReportScope = scope_toggle.value or "year"
            year: int | None = None
            if scope == "year":
                if year_input.value is None:
                    ui.notify("사업연도를 입력하세요.", type="warning")
                    return
                year = int(year_input.value)

            try:
                excel_bytes = await run.io_bound(
                    annual_report_service.export_report_excel,
                    scope,
                    year,
                )
                filename = annual_report_service.report_excel_filename(
                    scope, year
                )
            except ValueError as e:
                ui.notify(str(e), type="negative")
                return
            except Exception as e:
                ui.notify(f"엑셀 생성 실패: {e}", type="negative")
                return

            ui.download(excel_bytes, filename=filename)
            ui.notify("엑셀 다운로드를 시작합니다.", type="positive")

        def on_print() -> None:
            ui.run_javascript("window.print()")

        preview_btn.on_click(on_preview)
        export_btn.on_click(on_export)
        print_btn.on_click(on_print)
        render_idle("집계 범위와 연도를 선택한 뒤 미리보기, 엑셀 다운로드 또는 인쇄")
