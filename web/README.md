# 제주목장 React 앱

NiceGUI 파이썬 UI를 대체하는 웹 화면입니다. 데이터는 기존 Supabase 테이블을 API로 읽습니다.

## 실행

Node.js 18 이상이 필요합니다.

```bash
cd web
copy .env.example .env
```

`.env`에 Supabase 프로젝트 URL과 **anon/publishable 키**를 넣습니다. DB 비밀번호는 넣지 마세요.

```bash
npm install
npm run dev
```

브라우저에서 http://localhost:5173 을 엽니다.

## 권한

- 로그인하지 않아도 목록·상세는 조회됩니다.
- 등록/수정/삭제는 관리자만 가능합니다.
- Supabase Dashboard → Authentication → Users 에서 본인 계정을 만들고, App metadata에 아래를 넣으세요.

```json
{ "role": "admin" }
```

회원가입은 앱에서 열지 않습니다. 계정은 대시보드에서만 만드세요.

## 파이썬에 남는 기능

- horsepia 마적 실시간 조회
- 경주기록 전체 확인(스크래핑)
- 명단출력 시 캐시 없는 말의 horsepia 보강
