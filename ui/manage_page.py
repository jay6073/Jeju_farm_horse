"""
관리 화면 (아키텍처 프롬프트 4-2절).

쓰기 작업을 탭으로 나눠 한 화면에 모은다:
1. 개별 추가
2. 보유상태 변경 (다중 선택 + 상태/발생일자/직접입력 사유, 정상 복귀 포함)
3. 용도변경 (마종 변경, 위수탁마 제외)
4. 엑셀 일괄 업로드 (최초 등록용, 미리보기 확인 후 반영)

[통합 시 변경사항] 상단 탭 네비게이션 -> 좌측 사이드바로 전환.
"""
from __future__ import annotations

from datetime import date

from nicegui import events, run, ui

from models.horse import (
    HORSE_SPECIES,
    MANAGEABLE_STATUSES,
    STATUS_CUSTOM_OPTION,
    STATUS_MAX_LENGTH,
    STATUS_NORMAL,
    TRANSFERABLE_SPECIES,
    TRANSFER_TARGET_SPECIES,
    Horse,
    normalize_custom_status,
)
from repository.horse_repository import HorseRepository
from services import import_service
from services.import_service import ImportValidationError
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state, status_badge

# 위수탁마는 위탁 계약(entrustment_page.py)을 통해서만 등록 가능 — 개별 추가에서는 제외
MANAGEABLE_SPECIES = [s for s in HORSE_SPECIES if s != "위수탁마"]

_repo = HorseRepository()


@ui.page("/manage")
def manage_page() -> None:
    content = render_nav("/manage")
    with content:
        ui.label("보유마 관리").classes("text-lg sm:text-xl font-medium")

        with ui.tabs().props("dense").classes("w-full border-b border-gray-200") as tabs:
            tab_add = ui.tab("개별 추가").classes("flex-1 text-xs sm:text-sm px-1")
            tab_status = ui.tab("보유상태 변경").classes("flex-1 text-xs sm:text-sm px-1")
            tab_species = ui.tab("용도변경").classes("flex-1 text-xs sm:text-sm px-1")
            tab_import = ui.tab("엑셀 일괄 등록").classes("flex-1 text-xs sm:text-sm px-1")

        with ui.tab_panels(tabs, value=tab_add).classes("w-full p-1 sm:p-4"):
            with ui.tab_panel(tab_add):
                _build_add_section()
            with ui.tab_panel(tab_status):
                _build_status_change_section()
            with ui.tab_panel(tab_species):
                _build_species_change_section()
            with ui.tab_panel(tab_import):
                _build_import_section()


def _build_add_section() -> None:
    with ui.column().classes("w-full max-w-2xl gap-3"):
        name_input = ui.input(label="마명").classes("w-full")
        species_select = ui.select(options=MANAGEABLE_SPECIES, label="마종").classes("w-full")
        number_input = ui.input(label="마번 (horsepia 등록번호, 선택)").classes("w-full")
        breed_input = ui.input(label="품종코드 (선택)").classes("w-full")
        ui.label(
            "horsepia에서 이 말의 상세 페이지를 열어 URL의 hrsGbCd 값을 그대로 복사해 넣으세요. "
            "비워두면 조회 시 자동으로 찾아 저장됩니다."
        ).classes("text-xs text-gray-400")
        ui.label(
            "위수탁마는 여기서 등록할 수 없습니다. 위탁 계약 등록 화면을 이용하세요."
        ).classes("text-xs text-amber-600")

        def reset_form() -> None:
            name_input.value = ""
            species_select.value = None
            number_input.value = ""
            breed_input.value = ""

        async def on_save() -> None:
            if not name_input.value or not species_select.value:
                ui.notify("마명과 마종은 필수입니다.", type="warning")
                return
            try:
                horse = Horse(
                    마명=name_input.value,
                    마종=species_select.value,
                    마번=number_input.value or None,
                    품종코드=breed_input.value or None,
                )
            except ValueError as e:
                ui.notify(str(e), type="negative")
                return

            await run.io_bound(_repo.insert, horse)
            ui.notify(f"'{horse.마명}' 등록 완료", type="positive")
            reset_form()

        ui.button("+ 추가", on_click=on_save).props("color=primary")


def _build_status_change_section() -> None:
    checked_ids: set[int] = set()

    with ui.column().classes("w-full max-w-2xl gap-3"):
        species_select = ui.select(options=MANAGEABLE_SPECIES, label="마종").classes("w-full")
        list_container = ui.column().classes("w-full")
        form_container = ui.column().classes("w-full")

        async def render_list() -> None:
            list_container.clear()
            form_container.clear()
            checked_ids.clear()
            species = species_select.value
            if not species:
                return

            horses = await run.io_bound(_repo.get_all_by_species, species)
            with list_container:
                if not horses:
                    empty_state(f"{species}에 해당하는 보유마가 없습니다", icon="info")
                    return
                with ui.card().classes(CARD_CLASSES + " p-4"):
                    for horse in horses:
                        with ui.row().classes("items-center gap-3 w-full"):

                            def on_check(e, hid=horse.id) -> None:
                                if e.value:
                                    checked_ids.add(hid)
                                else:
                                    checked_ids.discard(hid)

                            ui.checkbox(on_change=on_check)
                            ui.label(horse.마명).classes("flex-1")
                            status_badge(horse.상태)
                            if horse.상태 != "정상" and horse.상태발생일자:
                                ui.label(horse.상태발생일자).classes(
                                    "text-xs text-gray-400"
                                )

            with form_container:
                with ui.card().classes(CARD_CLASSES + " p-4"):
                    ui.label("선택한 말들의 보유상태 변경").classes(
                        "text-sm text-gray-500 mb-2"
                    )
                    with ui.row().classes("w-full gap-3"):
                        status_select = ui.select(
                            options=MANAGEABLE_STATUSES, label="상태"
                        ).classes("flex-1")
                        date_input = ui.input(
                            label="발생일자", value=date.today().isoformat()
                        ).props("type=date").classes("flex-1")
                    reason_input = ui.input(
                        label="사유",
                        placeholder="예: 장기외박, 이송중",
                    ).props(f"maxlength={STATUS_MAX_LENGTH}").classes("w-full")
                    reason_input.set_visibility(False)

                    def _on_status_value_change() -> None:
                        is_normal = status_select.value == STATUS_NORMAL
                        is_custom = status_select.value == STATUS_CUSTOM_OPTION
                        date_input.set_visibility(not is_normal)
                        reason_input.set_visibility(is_custom)
                        if is_normal:
                            date_input.value = None
                        elif not date_input.value:
                            date_input.value = date.today().isoformat()
                        if not is_custom:
                            reason_input.value = ""

                    status_select.on_value_change(_on_status_value_change)

                    def on_change_status() -> None:
                        ids = list(checked_ids)
                        if not ids:
                            ui.notify("변경할 말을 선택하세요.", type="warning")
                            return
                        if not status_select.value:
                            ui.notify("변경할 상태를 선택하세요.", type="warning")
                            return

                        is_normal = status_select.value == STATUS_NORMAL
                        is_custom = status_select.value == STATUS_CUSTOM_OPTION
                        status_date = None if is_normal else date_input.value
                        if not is_normal and not status_date:
                            ui.notify("발생일자를 입력하세요.", type="warning")
                            return

                        if is_custom:
                            try:
                                new_status = normalize_custom_status(
                                    reason_input.value or ""
                                )
                            except ValueError as e:
                                ui.notify(str(e), type="warning")
                                return
                        else:
                            new_status = status_select.value

                        async def confirm() -> None:
                            dialog.close()
                            updated = await run.io_bound(
                                _repo.update_status_bulk,
                                ids,
                                new_status,
                                status_date,
                            )
                            ui.notify(f"{updated}마리 상태 변경 완료", type="positive")
                            await render_list()

                        if is_normal:
                            confirm_text = (
                                f"{len(ids)}마리를 보유중(정상)으로 "
                                f"복귀하시겠습니까?"
                            )
                            confirm_color = "primary"
                        else:
                            confirm_text = (
                                f"{len(ids)}마리를 [{new_status}]로 "
                                f"변경하시겠습니까? (발생일자: {status_date})"
                            )
                            confirm_color = "negative"

                        with ui.dialog() as dialog, ui.card():
                            ui.label(confirm_text)
                            with ui.row().classes("w-full justify-end gap-2"):
                                ui.button("취소", on_click=dialog.close).props("flat")
                                ui.button("확인", on_click=confirm).props(
                                    f"color={confirm_color}"
                                )
                        dialog.open()

                    ui.button("상태 변경", on_click=on_change_status).props(
                        "color=primary"
                    )

        species_select.on_value_change(render_list)


def _build_species_change_section() -> None:
    checked_ids: set[int] = set()

    with ui.column().classes("w-full max-w-2xl gap-3"):
        ui.label(
            "씨수말·교육마·관상마·기타마 사이에서 용도를 변경할 수 있습니다. "
            "위수탁마는 이 화면에서 변경할 수 없습니다."
        ).classes("text-xs text-gray-400 break-words w-full")

        species_select = ui.select(
            options=TRANSFERABLE_SPECIES, label="현재 마종"
        ).classes("w-full")
        list_container = ui.column().classes("w-full")
        form_container = ui.column().classes("w-full")

        async def render_list() -> None:
            list_container.clear()
            form_container.clear()
            checked_ids.clear()
            species = species_select.value
            if not species:
                return

            horses = await run.io_bound(_repo.get_all_by_species, species)
            target_options = [s for s in TRANSFER_TARGET_SPECIES if s != species]

            with list_container:
                if not horses:
                    empty_state(f"{species}에 해당하는 보유마가 없습니다", icon="info")
                    return
                with ui.card().classes(CARD_CLASSES + " p-4"):
                    for horse in horses:
                        with ui.row().classes("items-center gap-3 w-full"):

                            def on_check(e, hid=horse.id) -> None:
                                if e.value:
                                    checked_ids.add(hid)
                                else:
                                    checked_ids.discard(hid)

                            ui.checkbox(on_change=on_check)
                            ui.label(horse.마명).classes("flex-1")
                            status_badge(horse.상태)

            with form_container:
                if not target_options:
                    return
                with ui.card().classes(CARD_CLASSES + " p-4"):
                    ui.label("선택한 말들의 용도(마종) 변경").classes(
                        "text-sm text-gray-500 mb-2"
                    )
                    target_select = ui.select(
                        options=target_options, label="변경할 마종"
                    ).classes("w-full")

                    def on_change_species() -> None:
                        ids = list(checked_ids)
                        if not ids:
                            ui.notify("변경할 말을 선택하세요.", type="warning")
                            return
                        if not target_select.value:
                            ui.notify("변경할 마종을 선택하세요.", type="warning")
                            return

                        async def confirm() -> None:
                            dialog.close()
                            try:
                                updated = await run.io_bound(
                                    _repo.update_species_bulk,
                                    ids,
                                    target_select.value,
                                )
                            except ValueError as e:
                                ui.notify(str(e), type="negative")
                                return
                            ui.notify(
                                f"{updated}마리 용도변경 완료 "
                                f"({species} → {target_select.value})",
                                type="positive",
                            )
                            await render_list()

                        with ui.dialog() as dialog, ui.card():
                            ui.label(
                                f"{len(ids)}마리를 [{species}]에서 "
                                f"[{target_select.value}](으)로 변경하시겠습니까?"
                            )
                            with ui.row().classes("w-full justify-end gap-2"):
                                ui.button("취소", on_click=dialog.close).props("flat")
                                ui.button("확인", on_click=confirm).props(
                                    "color=primary"
                                )
                        dialog.open()

                    ui.button("용도 변경", on_click=on_change_species).props(
                        "color=primary"
                    )

        species_select.on_value_change(render_list)


def _build_import_section() -> None:
    parsed_rows: list = []

    with ui.column().classes("w-full max-w-2xl gap-3"):
        ui.label(
            "필수 컬럼: 마명, 마종, 등록번호 (품종코드는 선택 컬럼). "
            "등록번호·품종코드는 horsepia URL 값을 그대로 넣으세요."
        ).classes("text-xs text-gray-400 break-words w-full")

        preview_container = ui.column().classes("w-full")
        commit_container = ui.column().classes("w-full")

        async def on_upload(e: events.UploadEventArguments) -> None:
            preview_container.clear()
            commit_container.clear()
            parsed_rows.clear()

            try:
                if hasattr(e, 'content') and e.content:
                    file_bytes = e.content.read()
                elif hasattr(e, 'file'):
                    file_bytes = await e.file.read()
                else:
                    raise Exception("파일 데이터를 읽을 수 없습니다.")

                rows = await run.io_bound(import_service.parse_excel, file_bytes, _repo)

            except ImportValidationError as ex:
                with preview_container:
                    with ui.row().classes(
                        "items-center gap-2 py-3 px-4 bg-red-50 rounded-lg w-full"
                    ):
                        ui.icon("error").classes("text-red-500")
                        ui.label(str(ex)).classes("text-red-600 text-sm")
                return
            except Exception as ex:
                with preview_container:
                    with ui.row().classes(
                        "items-center gap-2 py-3 px-4 bg-red-50 rounded-lg w-full"
                    ):
                        ui.icon("warning").classes("text-red-500")
                        ui.label(f"엑셀 파일 읽기 실패: {str(ex)}").classes("text-red-600 text-sm")
                return

            parsed_rows.extend(rows)

            with preview_container:
                with ui.card().classes(CARD_CLASSES + " p-4 w-full"):
                    for r in rows:
                        with ui.row().classes(
                            "items-center gap-3 w-full text-sm py-1 border-b border-gray-100"
                        ):
                            ui.label(f"{r.row_no}행").classes("text-gray-400 w-12")
                            ui.label(r.마명 or "-").classes("flex-1")
                            ui.label(r.마종 or "-").classes("flex-1")
                            if r.error:
                                ui.label(r.error).classes("text-red-600 text-xs")
                            elif r.is_duplicate:
                                ui.label("중복 (건너뜀)").classes("text-orange-500 text-xs")
                            else:
                                ui.label("등록 예정").classes("text-green-600 text-xs")

            valid_count = sum(1 for r in rows if r.will_register)

            async def on_commit() -> None:
                inserted = await run.io_bound(
                    import_service.commit_rows, parsed_rows, _repo
                )
                ui.notify(f"{inserted}마리 일괄 등록 완료", type="positive")
                preview_container.clear()
                commit_container.clear()
                parsed_rows.clear()

            with commit_container:
                btn = ui.button(f"일괄 등록 ({valid_count}건)", on_click=on_commit).props(
                    "color=primary"
                ).classes("w-full sm:w-auto")
                if valid_count == 0:
                    btn.disable()

        ui.upload(
            on_upload=on_upload,
            auto_upload=True
        ).props(
            'flat bordered color=primary accept=.xlsx,.xls,.xlsm dense'
        ).classes(
            'w-full max-w-full rounded-xl border-2 border-dashed border-gray-300 bg-gray-50/50 hover:border-blue-400 transition-colors'
        )