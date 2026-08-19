export type HorseRow = {
  id: number;
  마번: string | null;
  마명: string;
  마종: string;
  품종코드: string | null;
  상태: string;
  상태발생일자: string | null;
  출생일: string | null;
  성별: string | null;
  부마명: string | null;
  모마명: string | null;
  최초등록일?: string | null;
  퇴사일?: string | null;
  profile_scraped_at: string | null;
};

export type EntrustmentRow = {
  horse_id: string;
  application_year: number | null;
  applicant_name: string | null;
  farm_name: string | null;
  farm_in_date: string | null;
  farm_out_date: string | null;
  entrustment_period: string | null;
  entrustment_fee: number | null;
  status: string;
  first_listed_date: string | null;
  first_result: string | null;
  final_listed_date: string | null;
  final_result: string | null;
  sire_name: string | null;
  sex: string | null;
  birth_date: string | null;
};

export type AuctionRow = {
  id: number;
  horse_id: string;
  auction_date: string | null;
  auction_name: string | null;
  hammer_price: number | null;
  buyer_name: string | null;
  is_final: boolean;
};

export type RaceRow = {
  id: number;
  horse_id: string;
  race_date: string | null;
  race_name: string | null;
  distance: number | null;
  grade: string | null;
  horse_number: number | null;
  rank: string | null;
  jockey: string | null;
  record_time: string | null;
  weight: string | null;
  horse_weight: number | null;
  track_condition: string | null;
};

export type CareerRow = {
  horse_id: string;
  total_starts: number;
  total_wins: number;
  win_rate: number;
  total_prize_money: number;
  rating: string | null;
  registered_name: string | null;
  data_source: string;
  last_scraped_at: string | null;
};
