"""
마종별 보유마 명단 미리보기·인쇄 화면.

컬럼: 마번, 마명, 출생일, 성별, 부마명, 모마명
- 일반 마종: 상태=정상 + horsepia 조회
- 위수탁마: 사업연도 + entrustment DB (스크래핑 없음, 모마명='-')
"""
from __future__ import annotations

from nicegui import run, ui

from models.horse import HORSE_SPECIES
from repository.horse_repository import HorseRepository
from services.print_service import (
    PRINT_COLUMNS,
    PRINT_COLUMNS_ENTRUSTMENT,
    SPECIES_ENTRUSTMENT,
    PrintRow,
    build_species_print_rows,
)
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state

_repo = HorseRepository()

_PRINT_STYLE = """
@media print {
  header, .q-drawer, .q-drawer__backdrop, .no-print {
    display: none !important;
  }
  body, .q-page, .nicegui-content {
    margin: 0 !important;
    padding: 0 !important;
  }
  .print-area {
    box-shadow: none !important;
    border: none !important;
  }
  .print-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11pt;
  }
  .print-table th,
  .print-table td {
    border: 1px solid #333;
    padding: 4px 8px;
    text-align: left;
  }
}
"""


@ui.page("/print", response_timeout=300)
def print_page() -> None:
    content = render_nav("/print")
    ui.add_css(_PRINT_STYLE)

    with content:
        with ui.row().classes("w-full items-center justify-between gap-3 no-print"):
            ui.label("마종별 명단 출력").classes("text-lg sm:text-xl font-medium")

        with ui.column().classes("w-full max-w-5xl gap-3"):
            with ui.row().classes("w-full gap-3 items-end no-print"):
                species_select = ui.select(
                    options=HORSE_SPECIES, label="마종"
                ).classes("flex-1")
                year_input = ui.number(label="사업연도").classes("w-36")
                year_input.set_visibility(False)
                preview_btn = ui.button("미리보기", icon="preview").props(
                    "color=primary"
                )
                print_btn = ui.button("인쇄", icon="print").props(
                    "outline color=primary"
                )
                print_btn.disable()

            ui.label(
                "일반 마종은 상태=정상만 포함하며, "
                "출생일·성별·부마명·모마명은 horsepia에서 조회합니다. "
                "위수탁마는 사업연도 선택 후 DB에서 바로 불러오며 "
                "신청인 컬럼이 추가됩니다 (모마명은 DB에 없어 '-' 표시)."
            ).classes("text-xs text-gray-400 no-print")

            result_container = ui.column().classes("w-full")

            def _on_species_change() -> None:
                is_entrust = species_select.value == SPECIES_ENTRUSTMENT
                year_input.set_visibility(is_entrust)
                if not is_entrust:
                    year_input.value = None

            species_select.on_value_change(_on_species_change)

            def render_idle(message: str) -> None:
                result_container.clear()
                print_btn.disable()
                with result_container:
                    empty_state(message, icon="print")

            def render_loading(species: str) -> None:
                result_container.clear()
                print_btn.disable()
                with result_container:
                    with ui.row().classes(
                        "w-full items-center gap-2 py-8 justify-center"
                    ):
                        ui.spinner(size="lg")
                        if species == SPECIES_ENTRUSTMENT:
                            msg = f"{species} 명단을 DB에서 불러오는 중..."
                        else:
                            msg = f"{species} 명단·마적을 불러오는 중..."
                        ui.label(msg).classes("text-gray-500 text-sm")

            def render_table(
                species: str,
                rows: list[PrintRow],
                *,
                application_year: int | None = None,
            ) -> None:
                result_container.clear()
                with result_container:
                    with ui.card().classes(CARD_CLASSES + " p-4 print-area"):
                        if species == SPECIES_ENTRUSTMENT and application_year:
                            title = f"{species} 명단 ({application_year}년)"
                            subtitle = f"출력 대상 {len(rows)}두 (사업연도 {application_year})"
                        else:
                            title = f"{species} 보유마 명단"
                            subtitle = f"출력 대상 {len(rows)}두 (상태=정상)"

                        ui.label(title).classes("text-base font-medium mb-1")
                        ui.label(subtitle).classes("text-xs text-gray-500 mb-3")

                        if not rows:
                            empty_state(
                                f"{species}에 해당하는 말이 없습니다",
                                icon="info",
                            )
                            print_btn.disable()
                            return

                        col_names = (
                            PRINT_COLUMNS_ENTRUSTMENT
                            if species == SPECIES_ENTRUSTMENT
                            else PRINT_COLUMNS
                        )
                        columns = [
                            {
                                "name": col,
                                "label": col,
                                "field": col,
                                "align": "left",
                            }
                            for col in col_names
                        ]
                        table_rows = [row.as_dict() for row in rows]
                        ui.table(
                            columns=columns,
                            rows=table_rows,
                            row_key="마번",
                        ).classes("w-full print-table").props(
                            "flat dense wrap-cells"
                        )

                        failed = [r for r in rows if r.error]
                        if failed:
                            with ui.column().classes("mt-3 gap-1 no-print"):
                                ui.label(
                                    f"마적 조회 실패 {len(failed)}두 "
                                    "(명단에는 '-'로 표시됨)"
                                ).classes("text-xs text-amber-600")

                print_btn.enable()

            async def on_preview() -> None:
                species = species_select.value
                if not species:
                    ui.notify("마종을 선택하세요.", type="warning")
                    return

                year: int | None = None
                if species == SPECIES_ENTRUSTMENT:
                    if year_input.value is None:
                        ui.notify("사업연도를 입력하세요.", type="warning")
                        return
                    year = int(year_input.value)

                render_loading(species)
                try:
                    rows = await run.io_bound(
                        build_species_print_rows,
                        species,
                        _repo,
                        year,
                    )
                except ValueError as e:
                    render_idle(str(e))
                    ui.notify(str(e), type="negative")
                    return

                render_table(species, rows, application_year=year)

            def on_print() -> None:
                ui.run_javascript("window.print()")

            preview_btn.on_click(on_preview)
            print_btn.on_click(on_print)
            render_idle("마종을 선택한 뒤 미리보기를 누르세요")
