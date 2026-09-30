"""인력현황 화면 — staff 테이블 CRUD + 인쇄.

- 목록은 수행업무파트별로 묶어서 표시 (지원파트→씨수말파트→전기육성파트→교육파트)
- 등록·수정은 같은 다이얼로그를 재사용
- 연락처는 010-0000-0000 형식만 허용 (화면 검증 + DB 제약 이중 방어)
- 인쇄: 업무파트별 구분은 화면과 동일하게 유지, 칼럼(직위/생년월일·나이/연락처)은 선택 가능
"""
from __future__ import annotations

import re
from datetime import date

from nicegui import run, ui

from repository.staff_repository import (
    DUTY_PARTS,
    create_staff,
    delete_staff,
    list_staff,
    update_staff,
)
from ui.nav import render_nav
from ui.theme import CARD_CLASSES, empty_state

PHONE_PATTERN = re.compile(r"^010-\d{4}-\d{4}$")

_PRINT_STYLE = """
@media print {
  @page {
    size: A4 portrait;
    margin: 12mm;
  }

  header, .q-drawer, .q-drawer__backdrop, .no-print,
  .q-dialog, .q-dialog__backdrop {
    display: none !important;
  }

  html, body,
  .q-layout, .q-page-container, .q-page,
  .nicegui-content {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    max-width: none !important;
    left: 0 !important;
  }

  .print-area {
    box-shadow: none !important;
    border: 1px solid #000 !important;
  }

  /* 인쇄 시 선택 해제한 칼럼 숨기기 (body에 붙는 클래스로 제어) */
  body.print-hide-position .col-position { display: none !important; }
  body.print-hide-birth    .col-birth    { display: none !important; }
  body.print-hide-contact  .col-contact  { display: none !important; }
}
"""


def _calc_age(birth: date) -> int:
    """만 나이."""
    today = date.today()
    age = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        age -= 1
    return age


@ui.page("/staff")
async def staff_page() -> None:
    content = render_nav("/staff")
    ui.add_css(_PRINT_STYLE)
    editing_id = None  # None이면 등록 모드, 값이 있으면 수정 모드

    with content:
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("인력현황").classes("text-xl font-medium")
            with ui.row().classes("items-center gap-3"):
                total_label = ui.label("").classes("text-sm text-gray-500")
                print_btn = ui.button("인쇄", icon="print").props(
                    "outline color=primary"
                ).classes("no-print")
                add_btn = ui.button("+ 인력 추가", icon="add").props(
                    "color=primary"
                ).classes("no-print")

        list_container = ui.column().classes("w-full gap-4 print-area")

        # ---- 등록/수정 다이얼로그 (재사용) ----
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md"):
            dialog_title = ui.label("인력 등록").classes("text-lg font-medium")
            name_input = ui.input(label="이름").classes("w-full")
            birth_input = ui.input(label="생년월일").props("type=date").classes("w-full")
            position_input = ui.input(label="직위").classes("w-full")
            contact_input = ui.input(
                label="연락처", placeholder="010-0000-0000"
            ).classes("w-full")
            part_select = ui.select(options=DUTY_PARTS, label="수행업무파트").classes(
                "w-full"
            )
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("취소", on_click=dialog.close).props("flat")
                save_btn = ui.button("저장").props("color=primary")

        # ---- 인쇄 옵션 다이얼로그 ----
        with ui.dialog() as print_dialog, ui.card():
            ui.label("인쇄할 칼럼 선택").classes("text-base font-medium")
            ui.checkbox("이름 (항상 포함)", value=True).props("disable")
            print_position_cb = ui.checkbox("직위", value=True)
            print_birth_cb = ui.checkbox("생년월일(나이)", value=True)
            print_contact_cb = ui.checkbox("연락처", value=True)
            ui.label("업무파트별로 구분되어 출력됩니다.").classes(
                "text-xs text-gray-400"
            )
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("취소", on_click=print_dialog.close).props("flat")
                print_confirm_btn = ui.button("인쇄").props("color=primary")

        async def refresh_list() -> None:
            list_container.clear()
            staff_list = await run.io_bound(list_staff)
            total_label.text = f"전체 {len(staff_list)}명"

            grouped: dict[str, list[dict]] = {part: [] for part in DUTY_PARTS}
            for s in staff_list:
                grouped.setdefault(s["duty_part"], []).append(s)

            with list_container:
                for part in DUTY_PARTS:
                    members = grouped.get(part, [])
                    ui.label(f"{part}  ({len(members)}명)").classes(
                        "text-sm text-gray-500 mt-2"
                    )
                    with ui.card().classes(CARD_CLASSES + " p-4"):
                        if not members:
                            empty_state("등록된 인력이 없습니다", icon="info")
                            continue
                        for s in members:
                            with ui.row().classes(
                                "items-center gap-3 w-full text-sm py-1 "
                                "border-b border-gray-100"
                            ):
                                ui.label(s["name"]).classes(
                                    "w-20 font-medium col-name"
                                )
                                ui.label(s["position"] or "-").classes(
                                    "w-32 text-gray-500 col-position"
                                )
                                age = _calc_age(s["birth_date"])
                                ui.label(f"{s['birth_date']} ({age}세)").classes(
                                    "w-40 text-gray-500 col-birth"
                                )
                                ui.label(s["contact"] or "-").classes(
                                    "w-32 text-gray-500 col-contact"
                                )
                                ui.space()
                                ui.button(
                                    icon="edit", on_click=lambda s=s: open_dialog(s)
                                ).props("flat dense round size=sm").classes(
                                    "no-print"
                                )
                                ui.button(
                                    icon="delete",
                                    on_click=lambda s=s: confirm_delete(s),
                                ).props(
                                    "flat dense round size=sm color=negative"
                                ).classes("no-print")

        def open_dialog(staff: dict | None = None) -> None:
            nonlocal editing_id
            editing_id = staff["id"] if staff else None
            dialog_title.text = "인력 수정" if staff else "인력 등록"
            name_input.value = staff["name"] if staff else ""
            birth_input.value = str(staff["birth_date"]) if staff else ""
            position_input.value = staff["position"] if staff else ""
            contact_input.value = staff["contact"] if staff else ""
            part_select.value = staff["duty_part"] if staff else None
            dialog.open()

        async def on_save() -> None:
            if not (name_input.value or "").strip():
                ui.notify("이름을 입력하세요.", type="warning")
                return
            if not birth_input.value:
                ui.notify("생년월일을 입력하세요.", type="warning")
                return
            if not part_select.value:
                ui.notify("수행업무파트를 선택하세요.", type="warning")
                return
            contact = (contact_input.value or "").strip()
            if contact and not PHONE_PATTERN.match(contact):
                ui.notify(
                    "연락처는 010-0000-0000 형식으로 입력하세요.", type="warning"
                )
                return
            try:
                birth = date.fromisoformat(birth_input.value)
            except ValueError:
                ui.notify("생년월일 형식이 올바르지 않습니다.", type="warning")
                return

            name = name_input.value.strip()
            position = (position_input.value or "").strip()
            part = part_select.value

            if editing_id is None:
                await run.io_bound(create_staff, name, birth, position, contact, part)
                ui.notify(f"'{name}' 등록 완료", type="positive")
            else:
                await run.io_bound(
                    update_staff, editing_id, name, birth, position, contact, part
                )
                ui.notify(f"'{name}' 수정 완료", type="positive")

            dialog.close()
            await refresh_list()

        save_btn.on_click(on_save)
        add_btn.on_click(lambda: open_dialog())

        def confirm_delete(staff: dict) -> None:
            async def on_confirm() -> None:
                confirm_dialog.close()
                await run.io_bound(delete_staff, staff["id"])
                ui.notify(f"'{staff['name']}' 삭제 완료", type="positive")
                await refresh_list()

            with ui.dialog() as confirm_dialog, ui.card():
                ui.label(f"'{staff['name']}'을(를) 삭제하시겠습니까?")
                ui.label("되돌릴 수 없습니다.").classes("text-xs text-gray-400")
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("취소", on_click=confirm_dialog.close).props("flat")
                    ui.button("삭제", on_click=on_confirm).props("color=negative")
            confirm_dialog.open()

        async def on_print() -> None:
            hide_classes = []
            if not print_position_cb.value:
                hide_classes.append("print-hide-position")
            if not print_birth_cb.value:
                hide_classes.append("print-hide-birth")
            if not print_contact_cb.value:
                hide_classes.append("print-hide-contact")
            hide_js = ",".join(f"'{c}'" for c in hide_classes)

            print_dialog.close()  # 인쇄 전에 다이얼로그를 먼저 닫는다
            await ui.run_javascript(
                f"""
                const keep = document.body.className
                    .split(' ')
                    .filter(c => c && !c.startsWith('print-hide-'));
                document.body.className = keep.concat([{hide_js}]).join(' ');
                await new Promise(r => setTimeout(r, 100));
                window.print();
                """
            )

        print_btn.on_click(print_dialog.open)
        print_confirm_btn.on_click(on_print)

        await refresh_list()
