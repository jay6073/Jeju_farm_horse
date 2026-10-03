"""
NiceGUI 앱 엔트리포인트.
현재 등록된 화면: main_page(조회), manage_page(관리), dashboard_page(대시보드),
print_page(명단출력), entrustment/auction/racing, profile_page(통합조회),
budget_compare_page(예산 비교), staff_page(인력현황).
"""

from dotenv import load_dotenv
load_dotenv()
import os
from pathlib import Path                                  # 추가

from nicegui import app, ui                               # app 추가

from ui import entrustment_page  # noqa: F401
from ui import main_page  # noqa: F401  (@ui.page 데코레이터 등록을 위한 import)
from ui import manage_page  # noqa: F401
from ui import dashboard_page  # noqa: F401
from ui import print_page  # noqa: F401
from ui import auction_page  # noqa: F401
from ui import racing_page  # noqa: F401
from ui import profile_page  # noqa: F401
from ui import budget_compare_page  # noqa: F401         # 추가
from ui import staff_page  # noqa: F401                  # 추가
from ui import holding_page  # noqa: F401
from ui.budget_api import router as budget_api_router    # 추가 (API)
from ui.theme import apply_global_theme

BASE_DIR = Path(__file__).resolve().parent                # 추가


# 예산 비교 프로그램(정적 파일) 서빙 — ui.run() 이전, 모듈 최상위에서 등록
app.add_static_files(                                     # 추가
    "/apps/budget-compare", str(BASE_DIR / "budget-compare")
)

# 예산 작업 저장/불러오기 API (/api/budget/...)
app.include_router(budget_api_router)                     # 추가 (API)


@ui.page("/")
def index() -> None:
    apply_global_theme()
    ui.navigate.to("/dashboard")

if __name__ in {"__main__", "__mp_main__"}:
    # Render 등 클라우드 배포 환경은 PORT 환경변수로 실제 포트를 지정해준다.
    # 로컬에서는 이 값이 없으니 기존처럼 8080을 그대로 쓴다.
    port = int(os.environ.get("PORT", 8080))
    ui.run(title="Jeju_farm_horse", host="0.0.0.0", port=port, reload=False)
