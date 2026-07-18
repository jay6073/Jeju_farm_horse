"""
관리 화면 (아키텍처 프롬프트 4-2절).

세 가지 쓰기 작업을 탭으로 나눠 한 화면에 모은다:
1. 개별 추가
2. 보유상태 변경 (다중 선택 + 상태/발생일자, 물리 삭제 없음)
3. 엑셀 일괄 업로드 (최초 등록용, 미리보기 확인 후 반영)
"""
from __future__ import annotations

from datetime import date

from nicegui import events, ui

from models.horse import HORSE_SPECIES, NON_NORMAL_STATUSES, Horse
from repository.horse_repository import HorseRepository
from services import import_service
from services.import_service import ImportValidationError
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, status_badge

_repo = HorseRepository()


@ui.page("/manage")
def manage_page() -> None:
    with ui.column().classes("w-full max-w-3xl mx-auto p-6 gap-6"):
        render_nav("/manage")
        ui.label("보유마 관리").classes("text-xl font-medium")

        with ui.tabs().classes("w-full") as tabs:
            tab_add = ui.tab("개별 추가")
            tab_status = ui.tab("보유상태 변경")
            tab_import = ui.tab("엑셀 일괄 등록")

        with ui.tab_panels(tabs, value=tab_add).classes("w-full"):
            with ui.tab_panel(tab_add):
                _build_add_section()
            with ui.tab_panel(tab_status):
                _build_status_change_section()
            with ui.tab_panel(tab_import):
                _build_import_section()


def _build_add_section() -> None:
    with ui.column().classes("w-full gap-3"):
        name_input = ui.input(label="마명").classes("w-full")
        species_select = ui.select(options=HORSE_SPECIES, label="마종").classes("w-full")
        number_input = ui.input(label="마번 (horsepia 등록번호, 선택)").classes("w-full")
        breed_input = ui.input(label="품종코드 (선택)").classes("w-full")
        ui.label(
            "horsepia에서 이 말의 상세 페이지를 열어 URL의 hrsGbCd 값을 그대로 복사해 넣으세요. "
            "비워두면 조회 시 자동으로 찾아 저장됩니다."
        ).classes("text-xs text-gray-400")

        def reset_form() -> None:
            name_input.value = ""
            species_select.value = None
            number_input.value = ""
            breed_input.value = ""

        def on_save() -> None:
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

            _repo.insert(horse)
            ui.notify(f"'{horse.마명}' 등록 완료", type="positive")
            reset_form()

        ui.button("+ 추가", on_click=on_save).props("color=primary")


def _build_status_change_section() -> None:
    checked_ids: set[int] = set()

    with ui.column().classes("w-full gap-3"):
        species_select = ui.select(options=HORSE_SPECIES, label="마종").classes("w-full")
        list_container = ui.column().classes("w-full")
        form_container = ui.column().classes("w-full")

        def render_list() -> None:
            list_container.clear()
            form_container.clear()
            checked_ids.clear()
            species = species_select.value
            if not species:
                return

            horses = _repo.get_all_by_species(species)
            with list_container:
                if not horses:
                    ui.label(f"{species}에 해당하는 보유마가 없습니다.").classes(
                        "text-gray-400 text-sm"
                    )
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
                            options=NON_NORMAL_STATUSES, label="상태"
                        ).classes("flex-1")
                        date_input = ui.date(value=date.today().isoformat()).classes(
                            "flex-1"
                        )

                    def on_change_status() -> None:
                        ids = list(checked_ids)
                        if not ids:
                            ui.notify("변경할 말을 선택하세요.", type="warning")
                            return
                        if not status_select.value:
                            ui.notify("변경할 상태를 선택하세요.", type="warning")
                            return
                        if not date_input.value:
                            ui.notify("발생일자를 입력하세요.", type="warning")
                            return

                        def confirm() -> None:
                            dialog.close()
                            updated = _repo.update_status_bulk(
                                ids, status_select.value, date_input.value
                            )
                            ui.notify(f"{updated}마리 상태 변경 완료", type="positive")
                            render_list()

                        with ui.dialog() as dialog, ui.card():
                            ui.label(
                                f"{len(ids)}마리를 [{status_select.value}]로 "
                                f"변경하시겠습니까? (발생일자: {date_input.value})"
                            )
                            with ui.row().classes("w-full justify-end gap-2"):
                                ui.button("취소", on_click=dialog.close).props("flat")
                                ui.button("확인", on_click=confirm).props(
                                    "color=negative"
                                )
                        dialog.open()

                    ui.button("상태 변경", on_click=on_change_status).props(
                        "color=primary"
                    )

        species_select.on_value_change(render_list)


def _build_import_section() -> None:
    parsed_rows: list = []

    with ui.column().classes("w-full gap-3"):
        ui.label(
            "필수 컬럼: 마명, 마종, 등록번호 (품종코드는 선택 컬럼). "
            "등록번호·품종코드는 horsepia URL 값을 그대로 넣으세요."
        ).classes("text-xs text-gray-400")

        preview_container = ui.column().classes("w-full")
        commit_container = ui.column().classes("w-full")

        def on_upload(e: events.UploadEventArguments) -> None:
            preview_container.clear()
            commit_container.clear()
            parsed_rows.clear()

            file_bytes = e.content.read()
            try:
                rows = import_service.parse_excel(file_bytes, _repo)
            except ImportValidationError as ex:
                with preview_container:
                    with ui.row().classes(
                        "items-center gap-2 py-3 px-4 bg-red-50 rounded-lg"
                    ):
                        ui.icon("error").classes("text-red-500")
                        ui.label(str(ex)).classes("text-red-600 text-sm")
                return

            parsed_rows.extend(rows)

            with preview_container:
                with ui.card().classes(CARD_CLASSES + " p-4"):
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

            def on_commit() -> None:
                inserted = import_service.commit_rows(parsed_rows, _repo)
                ui.notify(f"{inserted}마리 일괄 등록 완료", type="positive")
                preview_container.clear()
                commit_container.clear()
                parsed_rows.clear()

            with commit_container:
                btn = ui.button(f"일괄 등록 ({valid_count}건)", on_click=on_commit).props(
                    "color=primary"
                )
                if valid_count == 0:
                    btn.disable()

        ui.upload(on_upload=on_upload, auto_upload=True).props("accept=.xlsx,.xls")