import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useNotify } from "../components/Toast";
import { Card } from "../components/Card";

export function LoginPage() {
  const { signIn } = useAuth();
  const notify = useNotify();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await signIn(email, password);
      notify("로그인되었습니다");
      navigate("/");
    } catch (err) {
      notify(err instanceof Error ? err.message : "로그인에 실패했습니다", "err");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="mb-4 text-xl font-medium">관리자 로그인</h1>
      <Card>
        <form className="flex flex-col gap-3" onSubmit={onSubmit}>
          <label className="text-sm text-gray-500">
            이메일
            <input
              className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="text-sm text-gray-500">
            비밀번호
            <input
              className="mt-1 w-full rounded-md border border-gray-200 px-3 py-2"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-primary px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            로그인
          </button>
          <p className="text-xs text-gray-400">
            직원은 로그인하지 않아도 조회할 수 있습니다. 등록·수정은 관리자 계정만 가능합니다.
          </p>
        </form>
      </Card>
    </div>
  );
}
