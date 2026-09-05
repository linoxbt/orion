-- Orion's database, in one file.
--
-- This schema previously existed only inside the live Supabase project: it had
-- been created by hand, so a fresh deployment following REQUIREMENTS.md got as
-- far as its first write and stopped, and nobody could review the row-level
-- security or the quota function without opening the dashboard.
--
-- Apply it in Supabase's SQL editor, or with:
--     psql "$SUPABASE_DB_URL" -f migrations/001_init.sql
--
-- Every statement is idempotent, so running it against the existing project is
-- safe and is how you check the two agree.

-- ---------------------------------------------------------------------------
-- profiles
--
-- Keyed by the Dynamic user id (the session token's `sub`), not by a Supabase
-- auth user: identity comes from Dynamic, so auth.uid() is null in this
-- database. That is also why RLS below is a deny-all rather than an ownership
-- policy - there is no database-level identity to write one against.
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
    id                  text primary key,
    email               text,
    full_name           text,
    -- A data: URL of a picture the browser has already scaled to 320px. The
    -- API caps the field; this is the belt to that pair of braces.
    avatar_url          text,
    phone               text,
    country             text,
    address_line1       text,
    address_line2       text,
    city                text,
    region              text,
    postal_code         text,
    preferred_language  text not null default 'en',

    -- Where to reach this person mid-call. Per user, never per deployment.
    escalation_whatsapp text,
    escalation_email    text,

    -- Plan, and the free tier's monthly allowance. The month sits beside the
    -- count so the reset is a comparison rather than a scheduled job.
    plan                text not null default 'free' check (plan in ('free', 'pro')),
    bills_used          integer not null default 0,
    quota_month         text,
    plan_expires_at     timestamptz,
    payment_reference   text,

    -- The Paystack subscription behind a paid plan.
    subscription_code   text,
    subscription_status text,
    next_payment_at     timestamptz,

    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

-- Subscription lifecycle events carry no metadata of ours, so the code
-- recorded when the plan started is the only link back to an account.
create index if not exists profiles_subscription_code_idx
    on public.profiles (subscription_code)
    where subscription_code is not null;

-- Constraints are applied separately from the table, so an existing database
-- ends up with the same rules as a fresh one: `create table if not exists`
-- adds nothing to a table that already exists, which is how two deployments
-- quietly come to accept different data.
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'profiles_avatar_url_length') then
        alter table public.profiles add constraint profiles_avatar_url_length
            check (avatar_url is null or length(avatar_url) <= 200000);
    end if;
    if not exists (select 1 from pg_constraint where conname = 'profiles_bills_used_positive') then
        alter table public.profiles add constraint profiles_bills_used_positive
            check (bills_used >= 0);
    end if;
end
$$;

-- ---------------------------------------------------------------------------
-- negotiations
--
-- The Pydantic model is the source of truth and lives whole in `data`, so
-- adding a field to a negotiation needs no migration. The columns beside it
-- exist only to be queried on.
-- ---------------------------------------------------------------------------
create table if not exists public.negotiations (
    task_id      uuid primary key,
    user_id      text references public.profiles (id) on delete cascade,
    provider     text not null,
    phone_number text not null,
    vertical     text not null default 'cable_internet',
    language     text not null default 'en',
    status       text not null default 'pending',
    data         jsonb not null,
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now()
);

-- The dashboard's only query: this user's negotiations, newest first.
create index if not exists negotiations_user_created_idx
    on public.negotiations (user_id, created_at desc);

-- The renewals sweep and the operator console both filter on status.
create index if not exists negotiations_status_idx
    on public.negotiations (status);

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'negotiations_status_check') then
        alter table public.negotiations add constraint negotiations_status_check
            check (status in ('pending', 'calling', 'completed', 'failed'));
    end if;
end
$$;

-- ---------------------------------------------------------------------------
-- updated_at
-- ---------------------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
set search_path to ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists profiles_touch_updated_at on public.profiles;
create trigger profiles_touch_updated_at
    before update on public.profiles
    for each row execute function public.touch_updated_at();

drop trigger if exists negotiations_touch_updated_at on public.negotiations;
create trigger negotiations_touch_updated_at
    before update on public.negotiations
    for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------------
-- Row-level security: deny everything.
--
-- Deliberate, and it is the whole security model of this database. Identity
-- comes from Dynamic, so auth.uid() is null here and RLS cannot express "this
-- row belongs to the caller". Every read and write goes through the backend
-- with the service role, which scopes each query by a user id it has already
-- verified against Dynamic's JWKS. Enabling RLS with no permissive policy
-- means a leaked publishable/anon key opens nothing at all.
-- ---------------------------------------------------------------------------
alter table public.profiles     enable row level security;
alter table public.negotiations enable row level security;

-- Named so that a policy appearing here later is obviously a decision rather
-- than an accident.
drop policy if exists profiles_no_public_access     on public.profiles;
drop policy if exists negotiations_no_public_access on public.negotiations;

-- ---------------------------------------------------------------------------
-- The monthly allowance, spent atomically.
--
-- One statement, because doing the check and the increment separately let
-- several uploads at once all read the same count and all pass - and let the
-- account page saving a profile write a stale count back over it.
-- ---------------------------------------------------------------------------
create or replace function public.consume_bill_quota(
    p_user_id text,
    p_month   text,
    p_limit   integer
)
returns table (allowed boolean, used integer)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_plan    text;
    v_expires timestamptz;
    v_used    integer;
begin
    -- Create the row on first use, so a new account does not need a separate
    -- write before it can upload anything.
    insert into public.profiles (id) values (p_user_id)
    on conflict (id) do nothing;

    select plan, plan_expires_at,
           case when quota_month = p_month then bills_used else 0 end
      into v_plan, v_expires, v_used
      from public.profiles
     where id = p_user_id
       for update;

    -- A live paid plan is not metered at all.
    if v_plan = 'pro' and (v_expires is null or v_expires > now()) then
        return query select true, 0;
        return;
    end if;

    if v_used >= p_limit then
        return query select false, v_used;
        return;
    end if;

    update public.profiles
       set bills_used  = v_used + 1,
           quota_month = p_month
     where id = p_user_id;

    return query select true, v_used + 1;
end;
$$;

-- ---------------------------------------------------------------------------
-- Handing an allowance back when the work it paid for did not happen.
-- ---------------------------------------------------------------------------
create or replace function public.refund_bill_quota(
    p_user_id text,
    p_month   text
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    v_used integer;
begin
    update public.profiles
       set bills_used = greatest(0, bills_used - 1)
     where id = p_user_id
       and quota_month = p_month
       and bills_used > 0
    returning bills_used into v_used;

    return coalesce(v_used, 0);
end;
$$;

-- The service role is what the backend authenticates as; nothing else may
-- call these.
revoke all on function public.consume_bill_quota(text, text, integer) from public, anon, authenticated;
revoke all on function public.refund_bill_quota(text, text)           from public, anon, authenticated;
grant execute on function public.consume_bill_quota(text, text, integer) to service_role;
grant execute on function public.refund_bill_quota(text, text)           to service_role;

-- ---------------------------------------------------------------------------
-- Storage: call recordings.
--
-- Private. A recording is a phone call about somebody's account, so it is
-- served through short-lived signed links (app/services/recordings.py) rather
-- than a public URL. Files are keyed <user_id>/<task>-<call_sid>.mp3.
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('call-recordings', 'call-recordings', false)
on conflict (id) do update set public = false;
