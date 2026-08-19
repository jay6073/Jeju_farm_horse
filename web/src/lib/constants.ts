export const HORSE_SPECIES = [
  "씨수말",
  "교육마",
  "관상마",
  "위수탁마",
  "기타마",
] as const;

export const TRANSFERABLE_SPECIES = HORSE_SPECIES.filter((s) => s !== "위수탁마");
export const MANAGEABLE_SPECIES = TRANSFERABLE_SPECIES;

export const STATUS_NORMAL = "정상";
export const STATUS_CUSTOM_OPTION = "직접 입력";
export const MANAGEABLE_STATUSES = [STATUS_NORMAL, "폐사", "매각", STATUS_CUSTOM_OPTION];
export const STATUS_RESERVED = new Set([
  STATUS_NORMAL,
  "폐사",
  "위수탁종료",
  "매각",
  "기타",
  STATUS_CUSTOM_OPTION,
]);
export const STATUS_MAX_LENGTH = 30;

export const STATUS_ENTRUSTED = "위탁중";
export const STATUS_ENDED = "위탁종료";
export const HORSE_STATUS_OPTIONS = [STATUS_ENTRUSTED, STATUS_ENDED];

export const AUCTION_RESULTS = ["낙찰", "유찰", "미상장"] as const;

export const BREED_LABELS: Record<string, string> = {
  "00100": "더러브렛",
  "00200": "일반마",
  "00210": "일반마(승용전환)",
  "00300": "제주마(경주용)",
  "00310": "제주마(축진원)",
};

export const RECHECK_INTERVAL_DAYS = 7;
