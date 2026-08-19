-- Public read for staff without login; writes only for authenticated admin
-- (auth.jwt() -> app_metadata ->> role = 'admin').
-- Applied remotely via Supabase MCP; kept here for the React branch history.

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE
  public.horses,
  public.entrustment,
  public.auction_record,
  public.race_record,
  public.career_summary
FROM anon;

CREATE OR REPLACE FUNCTION public.is_app_admin()
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT coalesce((auth.jwt() -> 'app_metadata' ->> 'role') = 'admin', false);
$$;

REVOKE ALL ON FUNCTION public.is_app_admin() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_app_admin() TO authenticated, anon;
