-- A retry of the same request must return the run it already created, even when
-- the first run is still active.
--
-- `enqueue_agent_run` checked the idempotency key before taking the entitlement
-- row lock. Two concurrent deliveries of one request therefore both found
-- nothing, and the loser reached the concurrency check and failed with P0002
-- ("concurrent run limit reached") instead of replaying the winner's run. The
-- check now runs again under the lock, where it sees the winner's committed row.

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

  -- The lock serializes admissions per organization, so a concurrent delivery
  -- that lost the race is visible here and replays instead of failing.
  if target_idempotency_key is not null then
    select * into existing
    from public.agent_runs
    where organization_id = target_organization_id
      and idempotency_key = target_idempotency_key;
    if existing.id is not null then
      return existing;
    end if;
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
