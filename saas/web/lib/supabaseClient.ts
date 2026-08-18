import { createClient, SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/** Client Supabase, ou null si l'auth managee n'est pas encore configuree (mode dev). */
export const supabase: SupabaseClient | null =
  url && anon ? createClient(url, anon) : null;

export const supabaseConfigured = Boolean(url && anon);
