"""
보유현황 현황판 — 기준일 시점의 마종 × 관리파트 보유 두수 (미리보기·인쇄).
"""
from __future__ import annotations

from datetime import date

from nicegui import run, ui

from models.horse import STATUS_NORMAL
from repository.horse_repository import HorseRepository
from services.holding_status_service import build_holding_matrix
from ui.nav import render_nav
from ui.print_page import _PRINT_STYLE
from ui.theme import CARD_CLASSES, empty_state

_repo = HorseRepository()
_HOLDING_PAGE_STYLE = """
@media print {
  @page {
    size: A4 portrait;
    margin: 12mm;
  }
  .holding-cell-button {
    color: inherit !important;
    text-decoration: none !important;
  }
}
"""

@ui.page("/holding", response_timeout=300)
def holding_page() -> None:
    content = render_nav("/holding")
    ui.add_css(_PRINT_STYLE)
    ui.add_css(_HOLDING_PAGE_STYLE)

    with content:
        with ui.row().classes("w-full items-center justify-between gap-3 no-print"):
            ui.label("보유현황").classes("text-lg sm:text-xl font-medium")

        with ui.column().classes("w-full max-w-5xl gap-3"):
            with ui.row().classes("w-full gap-3 items-end no-print"):
                date_input = ui.input(
                    "기준날짜", value=date.today().isoformat()
                ).props("type=date outlined dense").classes("w-48")
                query_btn = ui.button("조회", icon="search").props("color=primary")
                print_btn = ui.button("인쇄", icon="print").props(
                    "outline color=primary"
                )
                print_btn.disable()

            ui.label(
                "기준일 당일에 폐사·매각·위탁종료 등으로 상태가 바뀐 말은 "
                "보유하지 않은 것으로 계산합니다. "
                "등록 이전 시점을 기준일로 넣으면 실제보다 많게 집계될 수 있습니다."
            ).classes("text-xs text-gray-400 no-print")

            result_container = ui.column().classes("w-full")

            def render_idle(message: str) -> None:
                result_container.clear()
                print_btn.disable()
                with result_container:
                    empty_state(message, icon="grid_view")

            def render_horse_dialog(title: str, horses: list) -> None:
                horses = sorted(horses, key=lambda horse: (horse.마번 or "", horse.마명 or ""))
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(title).classes("text-base font-medium")
                        ui.button(icon="close", on_click=dialog.close).props(
                            "flat round dense"
                        )
                    ui.label(f"{len(horses)}두").classes("text-xs text-gray-500")
                    if not horses:
                        empty_state("해당 말이 없습니다", icon="pets")
                    else:
                        with ui.column().classes("w-full max-h-[60vh] overflow-y-auto"):
                            with ui.row().classes(
                                "w-full text-xs text-gray-500 font-medium border-b py-2"
                            ):
                                ui.label("마번").classes("w-28 shrink-0")
                                ui.label("마명").classes("flex-1")
                            for horse in horses:
                                with ui.row().classes(
                                    "w-full items-center border-b border-gray-100 py-2"
                                ):
                                    ui.label(horse.마번 or "-").classes(
                                        "w-28 shrink-0 text-gray-500"
                                    )
                                    if horse.id is not None:
                                        ui.link(
                                            horse.마명 or "-",
                                            target=f"/main?horse_id={horse.id}",
                                        ).classes("flex-1 text-primary")
                                    else:
                                        ui.label(horse.마명 or "-").classes("flex-1")
                dialog.open()

            def render_matrix(as_of: date, m) -> None:
                result_container.clear()
                show_unassigned = m.unassigned_count > 0

                columns = [
                    {"name": "마종", "label": "마종", "field": "마종", "align": "left"},
                    *[
                        {"name": p, "label": p, "field": p, "align": "right"}
                        for p in m.duty_parts
                    ],
                ]
                if show_unassigned:
                    columns.append(
                        {"name": "미지정", "label": "미지정", "field": "미지정", "align": "right"}
                    )
                columns.append(
                    {"name": "합계", "label": "합계", "field": "합계", "align": "right"}
                )

                rows = []
                for s in m.species_list:
                    row = {"마종": s}
                    for p in m.duty_parts:
                        row[p] = m.counts.get((s, p), 0)
                    if show_unassigned:
                        row["미지정"] = m.unassigned_by_species.get(s, 0)
                    row["합계"] = m.row_totals.get(s, 0)
                    rows.append(row)

                total_row = {"마종": "합계"}
                for p in m.duty_parts:
                    total_row[p] = m.col_totals.get(p, 0)
                if show_unassigned:
                    total_row["미지정"] = m.unassigned_count
                total_row["합계"] = m.grand_total
                rows.append(total_row)

                with result_container:
                    with ui.card().classes(CARD_CLASSES + " p-4 print-area"):
                        ui.label("보유현황").classes("text-base font-medium mb-1")
                        ui.label(
                            f"기준일 {as_of:%Y-%m-%d} · 총 {m.grand_total}두"
                        ).classes("text-xs text-gray-500 mb-3")

                        table = ui.table(
                            columns=columns,
                            rows=rows,
                            row_key="마종",
                            pagination={"rowsPerPage": 0},
                        ).classes("w-full print-table").props(
                            "flat dense hide-pagination"
                        )
                        table.add_slot(
                            "body",
                            """
                            <q-tr :props="props"
                                  :class="props.row.마종 === '합계' ? 'bg-grey-2 text-weight-bold' : ''">
                              <q-td v-for="col in props.cols" :key="col.name" :props="props">
                                <template v-if="col.name === '마종'">{{ col.value }}</template>
                                <q-btn v-else flat dense no-caps
                                       class="holding-cell-button q-pa-none"
                                       :label="String(col.value)"
                                       :disable="Number(col.value) === 0"
                                       @click="$parent.$emit('open-horses', [props.row.마종, col.name])" />
                              </q-td>
                            </q-tr>
                            """,
                        )

                        def on_cell_click(event) -> None:
                            species, column = event.args
                            horses = [horse for horse in m.horses if horse.마종 == species or species == "합계"]
                            if column in m.duty_parts:
                                horses = [horse for horse in horses if horse.관리파트 == column]
                            elif column == "미지정":
                                horses = [horse for horse in horses if horse.관리파트 not in m.duty_parts]
                            title = f"{species} · {column} · {len(horses)}두"
                            render_horse_dialog(title, horses)

                        table.on("open-horses", on_cell_click)

                        if show_unassigned:
                            with ui.column().classes("mt-3 gap-0"):
                                ui.label("※ 미지정 사유").classes("text-xs text-gray-600")
                                for (species, status), n in sorted(
                                    m.unassigned_reasons.items()
                                ):
                                    if status == STATUS_NORMAL:
                                        reason = "정상 상태이나 관리파트가 지정되지 않음"
                                    else:
                                        reason = (
                                            f"기준일 이후 '{status}' 처리되어 "
                                            "관리파트 지정 대상에서 제외됨"
                                        )
                                    ui.label(
                                        f"- {species} {n}두: {reason}"
                                    ).classes("text-xs text-gray-600")
                print_btn.enable()

            async def on_query() -> None:
                try:
                    as_of = date.fromisoformat(str(date_input.value))
                except ValueError:
                    ui.notify("기준날짜를 확인하세요.", type="warning")
                    return
                result_container.clear()
                print_btn.disable()
                with result_container:
                    with ui.row().classes(
                        "w-full items-center gap-2 py-8 justify-center"
                    ):
                        ui.spinner(size="lg")
                        ui.label("보유현황을 집계하는 중...").classes(
                            "text-gray-500 text-sm"
                        )
                m = await run.io_bound(build_holding_matrix, as_of, _repo)
                render_matrix(as_of, m)

            def on_print() -> None:
                ui.run_javascript("window.print()")

            query_btn.on_click(on_query)
            print_btn.on_click(on_print)
            render_idle("기준날짜를 선택한 뒤 조회를 누르세요")
