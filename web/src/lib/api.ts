import { supabase } from "./supabase";
import type {
  AuctionRow,
  CareerRow,
  EntrustmentRow,
  HorseRow,
  RaceRow,
} from "./types";

const LIMIT = 5000;

function mapDbError(message: string): string {
  const text = message.toLowerCase();
  if (text.includes("row-level security") || text.includes("rls")) {
    return "저장 권한이 없습니다. 관리자 로그인 후 App metadata에 role=admin 이 있는지 확인하세요.";
  }
  if (text.includes("duplicate") || text.includes("unique")) {
    return "이미 같은 마번(또는 중복 키)이 등록되어 있습니다.";
  }
  if (text.includes("foreign key") || text.includes("violates foreign key")) {
    return "연결된 보유마(마번)가 없어 저장할 수 없습니다.";
  }
  if (text.includes("invalid input syntax for type date") || text.includes("date/time")) {
    return "날짜 형식이 올바르지 않습니다.";
  }
  return message;
}

function emptyToNull<T>(value: T): T | null {
  if (value == null) return null;
  if (typeof value === "string" && value.trim() === "") return null;
  return value;
}

async function must<T>(
  promise: PromiseLike<{ data: T | null; error: { message: string } | null }>,
): Promise<T> {
  const { data, error } = await promise;
  if (error) throw new Error(mapDbError(error.message));
  if (data == null) throw new Error("서버 응답이 비어 있습니다.");
  return data;
}

async function exec(
  promise: PromiseLike<{ error: { message: string } | null }>,
): Promise<void> {
  const { error } = await promise;
  if (error) throw new Error(mapDbError(error.message));
}

export async function listHorses(): Promise<HorseRow[]> {
  return must(
    supabase.from("horses").select("*").order("마종").order("마명").limit(LIMIT),
  );
}

export async function getHorseById(id: number): Promise<HorseRow | null> {
  const rows = await must<HorseRow[]>(
    supabase.from("horses").select("*").eq("id", id).limit(1),
  );
  return rows[0] ?? null;
}

export async function insertHorse(row: {
  마명: string;
  마종: string;
  마번?: string | null;
  품종코드?: string | null;
  상태?: string;
  상태발생일자?: string | null;
}): Promise<void> {
  await exec(
    supabase.from("horses").insert({
      마명: row.마명,
      마종: row.마종,
      마번: emptyToNull(row.마번 ?? null),
      품종코드: emptyToNull(row.품종코드 ?? null),
      상태: row.상태 ?? "정상",
      상태발생일자: emptyToNull(row.상태발생일자 ?? null),
    }),
  );
}

export async function insertHorses(
  rows: Array<{
    마명: string;
    마종: string;
    마번?: string | null;
    품종코드?: string | null;
    상태?: string;
  }>,
): Promise<void> {
  if (!rows.length) return;
  await exec(
    supabase.from("horses").insert(
      rows.map((row) => ({
        마명: row.마명,
        마종: row.마종,
        마번: emptyToNull(row.마번 ?? null),
        품종코드: emptyToNull(row.품종코드 ?? null),
        상태: row.상태 ?? "정상",
      })),
    ),
  );
}

export async function updateHorseStatus(
  ids: number[],
  상태: string,
  상태발생일자: string | null,
): Promise<void> {
  if (!ids.length) return;
  await exec(
    supabase.from("horses").update({ 상태, 상태발생일자: emptyToNull(상태발생일자) }).in("id", ids),
  );
}

export async function updateHorseSpecies(ids: number[], 마종: string): Promise<void> {
  if (!ids.length) return;
  await exec(supabase.from("horses").update({ 마종 }).in("id", ids));
}

export async function listEntrustment(): Promise<EntrustmentRow[]> {
  return must(supabase.from("entrustment").select("*").limit(LIMIT));
}

export async function getEntrustment(horseId: string): Promise<EntrustmentRow | null> {
  const rows = await must<EntrustmentRow[]>(
    supabase.from("entrustment").select("*").eq("horse_id", horseId).limit(1),
  );
  return rows[0] ?? null;
}

export async function insertEntrustment(
  row: Partial<EntrustmentRow> & { horse_id: string },
): Promise<void> {
  await exec(
    supabase.from("entrustment").insert({
      ...row,
      farm_in_date: emptyToNull(row.farm_in_date ?? null),
      farm_out_date: emptyToNull(row.farm_out_date ?? null),
      first_listed_date: emptyToNull(row.first_listed_date ?? null),
      final_listed_date: emptyToNull(row.final_listed_date ?? null),
      birth_date: emptyToNull(row.birth_date ?? null),
      applicant_name: emptyToNull(row.applicant_name ?? null),
      farm_name: emptyToNull(row.farm_name ?? null),
    }),
  );
}

export async function updateEntrustment(
  horseId: string,
  fields: Partial<EntrustmentRow>,
): Promise<void> {
  const cleaned: Partial<EntrustmentRow> = { ...fields };
  for (const key of ["farm_in_date", "farm_out_date", "first_listed_date", "final_listed_date", "birth_date"] as const) {
    if (key in cleaned) {
      cleaned[key] = emptyToNull(cleaned[key] ?? null) as never;
    }
  }
  await exec(supabase.from("entrustment").update(cleaned).eq("horse_id", horseId));
}

export async function deleteEntrustment(horseId: string): Promise<void> {
  await exec(supabase.from("entrustment").delete().eq("horse_id", horseId));
}

export async function listAuctions(): Promise<AuctionRow[]> {
  return must(
    supabase.from("auction_record").select("*").order("auction_date", { ascending: false }).limit(LIMIT),
  );
}

export async function listAuctionsForHorse(horseId: string): Promise<AuctionRow[]> {
  return must(
    supabase
      .from("auction_record")
      .select("*")
      .eq("horse_id", horseId)
      .order("auction_date", { ascending: true }),
  );
}

export async function insertAuction(row: Omit<AuctionRow, "id">): Promise<AuctionRow> {
  return must(
    supabase
      .from("auction_record")
      .insert({
        ...row,
        auction_date: emptyToNull(row.auction_date),
        buyer_name: emptyToNull(row.buyer_name),
      })
      .select("*")
      .single(),
  );
}

export async function updateAuction(id: number, fields: Partial<AuctionRow>): Promise<void> {
  const payload: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined || key === "id") continue;
    payload[key] = key === "auction_date" || key === "buyer_name" ? emptyToNull(value) : value;
  }
  await exec(supabase.from("auction_record").update(payload).eq("id", id));
}

export async function unsetFinalExcept(horseId: string, exceptId: number): Promise<void> {
  await exec(
    supabase
      .from("auction_record")
      .update({ is_final: false })
      .eq("horse_id", horseId)
      .neq("id", exceptId),
  );
}

export async function deleteAuction(id: number): Promise<void> {
  await exec(supabase.from("auction_record").delete().eq("id", id));
}

export async function listCareers(): Promise<CareerRow[]> {
  return must(supabase.from("career_summary").select("*").limit(LIMIT));
}

export async function getCareer(horseId: string): Promise<CareerRow | null> {
  const rows = await must<CareerRow[]>(
    supabase.from("career_summary").select("*").eq("horse_id", horseId).limit(1),
  );
  return rows[0] ?? null;
}

export async function listRacesForHorse(horseId: string): Promise<RaceRow[]> {
  return must(
    supabase
      .from("race_record")
      .select("*")
      .eq("horse_id", horseId)
      .order("race_date", { ascending: false }),
  );
}

export async function deleteRacesForHorse(horseId: string): Promise<void> {
  await exec(supabase.from("race_record").delete().eq("horse_id", horseId));
}

export async function deleteCareer(horseId: string): Promise<void> {
  await exec(supabase.from("career_summary").delete().eq("horse_id", horseId));
}

export async function deleteHorseByNumber(마번: string): Promise<void> {
  await exec(supabase.from("horses").delete().eq("마번", 마번));
}
