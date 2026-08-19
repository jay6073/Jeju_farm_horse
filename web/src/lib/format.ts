export function fmtDate(value: string | null | undefined): string {
  if (!value) return "-";
  return String(value).slice(0, 10);
}

export function fmtText(value: string | number | null | undefined): string {
  if (value == null) return "-";
  const text = String(value).trim();
  return text || "-";
}

export function fmtFee(value: number | null | undefined): string {
  if (value == null) return "-";
  return `${Number(value).toLocaleString("ko-KR")}`;
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function getBreedLabel(code: string | null | undefined): string {
  if (!code) return "-";
  const labels: Record<string, string> = {
    "00100": "더러브렛",
    "00200": "일반마",
    "00210": "일반마(승용전환)",
    "00300": "제주마(경주용)",
    "00310": "제주마(축진원)",
  };
  return labels[code] ?? `${code}(확인필요)`;
}

export function classifyAuction(firstResult: unknown, finalResult: unknown): string {
  const slots = [firstResult, finalResult]
    .map((v) => (v == null ? "" : String(v).trim()))
    .filter((s) => s && s !== "-");
  if (slots.length === 0) return "미상장";
  if (slots.some((s) => s.startsWith("낙찰"))) return "낙찰";
  if (slots.some((s) => s === "유찰" || s === "계약해지")) return "유찰";
  return "미상장";
}

export function hammerPriceFromResult(firstResult: unknown, finalResult: unknown): number {
  const re = /낙찰\s*\(([\d,]+)\)/;
  for (const r of [finalResult, firstResult]) {
    const text = r == null ? "" : String(r).trim();
    if (text.startsWith("낙찰")) {
      const match = re.exec(text);
      if (match) return Number(match[1].replaceAll(",", ""));
    }
  }
  return 0;
}
