export function normalizeHorseNumber(raw: string | null | undefined): string | null {
  if (raw == null) return null;
  let cleaned = String(raw).trim();
  if (!cleaned) return null;
  if (cleaned.endsWith(".0")) cleaned = cleaned.slice(0, -2);
  if (!/^\d+$/.test(cleaned)) return cleaned;
  return cleaned.padStart(7, "0");
}

export function normalizeApplicantName(name: string | null | undefined): string {
  const text = (name ?? "").trim();
  if (!text) return "(신청인 미상)";
  return text.replaceAll("㈜", "(주)").replace(/\s+/g, "");
}
