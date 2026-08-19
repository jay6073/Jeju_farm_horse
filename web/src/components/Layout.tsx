import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const PAGES = [
  { to: "/", label: "대시보드" },
  { to: "/main", label: "조회" },
  { to: "/manage", label: "관리" },
  { to: "/print", label: "명단출력" },
  { to: "/entrustment", label: "위탁관리" },
  { to: "/auction", label: "경매관리" },
  { to: "/racing", label: "경주성적" },
  { to: "/profile", label: "통합조회" },
];

export function Layout() {
  const { user, isAdmin, signOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  return (
    <div className="min-h-screen bg-white">
      <header className="no-print flex items-center justify-between border-b border-gray-200 bg-white px-2 py-2 text-gray-700">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="rounded-md p-2 text-gray-700 hover:bg-gray-100 lg:hidden"
            onClick={() => setOpen((v) => !v)}
          >
            메뉴
          </button>
          <span className="text-lg font-bold">제주목장</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          {user ? (
            <>
              <span className="hidden text-gray-500 sm:inline">{isAdmin ? "관리자" : "로그인됨"}</span>
              <button
                type="button"
                className="rounded-md px-2 py-1 text-gray-500 hover:bg-gray-100"
                onClick={async () => {
                  await signOut();
                  navigate("/");
                }}
              >
                로그아웃
              </button>
            </>
          ) : (
            <button
              type="button"
              className="rounded-md px-2 py-1 text-primary hover:bg-blue-50"
              onClick={() => navigate("/login")}
            >
              관리자 로그인
            </button>
          )}
        </div>
      </header>

      <div className="flex">
        {open ? (
          <button
            type="button"
            className="fixed inset-0 z-20 bg-black/20 lg:hidden"
            onClick={() => setOpen(false)}
          />
        ) : null}
        <aside
          className={`no-print z-30 border-r border-gray-200 bg-white px-3 py-4 ${
            open ? "fixed inset-y-0 left-0 w-56" : "hidden"
          } lg:sticky lg:top-0 lg:block lg:h-screen lg:w-56`}
        >
          <nav className="flex flex-col gap-1">
            {PAGES.map((page, index) => (
              <div key={page.to}>
                {index === 4 ? <div className="my-2 border-t border-gray-200" /> : null}
                <NavLink
                  to={page.to}
                  end={page.to === "/"}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center rounded-md px-3 py-2 text-sm no-underline transition-colors hover:bg-gray-100 ${
                      isActive ? "bg-primary/10 font-medium text-primary" : "text-gray-500"
                    }`
                  }
                >
                  {page.label}
                </NavLink>
              </div>
            ))}
          </nav>
        </aside>
        <main className="min-w-0 flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
