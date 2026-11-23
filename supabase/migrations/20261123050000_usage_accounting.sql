-- Corrective migration: atomic usage accounting.
-- Inserts a usage event idempotently and increments the tenant's consumed credits
-- in the same transaction. Server-owned: callable only by service_role.

create or replace function public.record_usage_event(
  target_organization_id uuid,
  target_actor_user_id uuid,
  target_event_type text,
  target_quantity numeric,
  target_credits numeric,
  target_idempotency_key text,
  target_metadata jsonb default '{}'::jsonb
)
returns public.usage_events
language plpgsql
security definer
set search_path = public
as $$
declare
  inserted public.usage_events;
begin
  if target_quantity < 0 or target_credits < 0 then
    raise exception using errcode = '22023', message = 'quantity and credits must be non-negative';
  end if;

  insert into public.usage_events (
    organization_id, actor_user_id, event_type, quantity, idempotency_key, metadata
  )
  values (
    target_organization_id, target_actor_user_id, target_event_type,
    target_quantity, target_idempotency_key, coalesce(target_metadata, '{}'::jsonb)
  )
  on conflict (organization_id, idempotency_key) do nothing
  returning * into inserted;

  if inserted.id is null then
    select * into inserted
    from public.usage_events
    where organization_id = target_organization_id
      and idempotency_key = target_idempotency_key;
    return inserted;
  end if;

  update public.organization_entitlements
  set credits_used = credits_used + target_credits,
      updated_at = timezone('utc', now())
  where organization_id = target_organization_id;

  return inserted;
end;
$$;

revoke all on function public.record_usage_event(uuid, uuid, text, numeric, numeric, text, jsonb) from public;
revoke all on function public.record_usage_event(uuid, uuid, text, numeric, numeric, text, jsonb) from anon;
revoke all on function public.record_usage_event(uuid, uuid, text, numeric, numeric, text, jsonb) from authenticated;
grant execute on function public.record_usage_event(uuid, uuid, text, numeric, numeric, text, jsonb) to service_role;
