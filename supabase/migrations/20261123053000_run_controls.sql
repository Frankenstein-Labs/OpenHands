-- Atomic run admission and settlement.
--
-- Run creation used to read the entitlement, count active runs and insert the
-- row in three separate requests, so two concurrent requests could both pass and
-- overspend or exceed the concurrency limit. `enqueue_agent_run` does the whole
-- decision under a row lock on the entitlement.

alter table public.organization_entitlements
  add column if not exists credits_reserved numeric(20, 6) not null default 0
    check (credits_reserved >= 0);

alter table public.agent_runs
  add column if not exists idempotency_key text;

create unique index if not exists agent_runs_org_idempotency_idx
  on public.agent_runs (organization_id, idempotency_key)
  where idempotency_key is not null;

create or replace function public.enqueue_agent_run(
  target_organization_id uuid,
  target_agent_id uuid,
  target_model_id text,
  target_conversation_id text,
  target_prompt text,
  target_budget_credits numeric,
  target_idempotency_key text,
  target_metadata jsonb default '{}'::jsonb
)
returns public.agent_runs
language plpgsql
security definer
set search_path = public
as $$
declare
  entitlement public.organization_entitlements;
  plan_limits jsonb;
  max_concurrent integer;
  active_count integer;
  existing public.agent_runs;
  created public.agent_runs;
begin
  if target_budget_credits is null or target_budget_credits <= 0 then
    raise exception using errcode = '22023', message = 'budget_credits must be positive';
  end if;
  if not public.is_org_member(target_organization_id) then
    raise exception using errcode = '42501', message = 'not a member of this organization';
  end if;

  if target_idempotency_key is not null then
    select * into existing
    from public.agent_runs
    where organization_id = target_organization_id
      and idempotency_key = target_idempotency_key;
    if existing.id is not null then
      return existing;
    end if;
  end if;

  select * into entitlement
  from public.organization_entitlements
  where organization_id = target_organization_id
  for update;

  if entitlement.organization_id is null then
    raise exception using errcode = 'P0001', message = 'organization has no entitlement';
  end if;
  if entitlement.status not in ('trialing', 'active') then
    raise exception using errcode = 'P0001', message = 'entitlement is not active';
  end if;

  select coalesce(limits, '{}'::jsonb) into plan_limits
  from public.plans where id = entitlement.plan_id;
  max_concurrent := coalesce((plan_limits ->> 'max_concurrent_runs')::integer, 1);

  select count(*) into active_count
  from public.agent_runs
  where organization_id = target_organization_id
    and status in ('queued', 'provisioning', 'running', 'waiting');
  if active_count >= max_concurrent then
    raise exception using errcode = 'P0002', message = 'concurrent run limit reached';
  end if;

  if entitlement.credits_used + entitlement.credits_reserved + target_budget_credits
     > entitlement.credits_limit then
    raise exception using errcode = 'P0003', message = 'insufficient credits';
  end if;

  update public.organization_entitlements
  set credits_reserved = credits_reserved + target_budget_credits,
      updated_at = timezone('utc', now())
  where organization_id = target_organization_id;

  insert into public.agent_runs (
    organization_id, agent_id, model_id, conversation_id, prompt, status,
    budget_credits, credits_reserved, idempotency_key, metadata, created_by
  )
  values (
    target_organization_id, target_agent_id, target_model_id, target_conversation_id,
    target_prompt, 'queued', target_budget_credits, target_budget_credits,
    target_idempotency_key, coalesce(target_metadata, '{}'::jsonb), (select auth.uid())
  )
  returning * into created;

  return created;
exception
  when unique_violation then
    select * into existing
    from public.agent_runs
    where organization_id = target_organization_id
      and idempotency_key = target_idempotency_key;
    return existing;
end;
$$;

-- Releases the reservation and books the real consumption. Idempotent: a run
-- already in a terminal state is returned unchanged.
create or replace function public.settle_agent_run(
  target_run_id uuid,
  target_status text,
  target_credits_used numeric,
  target_error text default null
)
returns public.agent_runs
language plpgsql
security definer
set search_path = public
as $$
declare
  run public.agent_runs;
  settled public.agent_runs;
begin
  if target_status not in ('completed', 'failed', 'cancelled', 'expired') then
    raise exception using errcode = '22023', message = 'target_status must be terminal';
  end if;
  if target_credits_used is null or target_credits_used < 0 then
    raise exception using errcode = '22023', message = 'credits_used must be non-negative';
  end if;

  select * into run from public.agent_runs where id = target_run_id for update;
  if run.id is null then
    raise exception using errcode = 'P0004', message = 'run not found';
  end if;
  if run.status in ('completed', 'failed', 'cancelled', 'expired') then
    return run;
  end if;

  update public.organization_entitlements
  set credits_reserved = greatest(credits_reserved - run.credits_reserved, 0),
      credits_used = credits_used + target_credits_used,
      updated_at = timezone('utc', now())
  where organization_id = run.organization_id;

  update public.agent_runs
  set status = target_status,
      credits_used = target_credits_used,
      credits_reserved = 0,
      error = coalesce(target_error, error),
      finished_at = timezone('utc', now()),
      updated_at = timezone('utc', now())
  where id = target_run_id
  returning * into settled;

  return settled;
end;
$$;

revoke all on function public.enqueue_agent_run(uuid, uuid, text, text, text, numeric, text, jsonb) from public;
revoke all on function public.enqueue_agent_run(uuid, uuid, text, text, text, numeric, text, jsonb) from anon;
grant execute on function public.enqueue_agent_run(uuid, uuid, text, text, text, numeric, text, jsonb) to authenticated;

revoke all on function public.settle_agent_run(uuid, text, numeric, text) from public;
revoke all on function public.settle_agent_run(uuid, text, numeric, text) from anon;
revoke all on function public.settle_agent_run(uuid, text, numeric, text) from authenticated;
grant execute on function public.settle_agent_run(uuid, text, numeric, text) to service_role;
