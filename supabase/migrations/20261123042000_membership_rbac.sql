-- Membership mutations are server-checked and transactionally protected.
-- Direct client writes are removed; the API invokes only these constrained functions.

drop policy if exists memberships_manage_admin on public.organization_memberships;

create or replace function public.add_organization_member(
  target_organization_id uuid,
  target_user_id uuid,
  target_role text
)
returns public.organization_memberships
language plpgsql
security definer
set search_path = public
as $$
declare
  actor_role text;
  created_membership public.organization_memberships;
begin
  select role into actor_role
  from public.organization_memberships
  where organization_id = target_organization_id and user_id = (select auth.uid());

  if actor_role is null or actor_role not in ('owner', 'admin') then
    raise exception using errcode = '42501', message = 'Insufficient organization permissions';
  end if;
  if target_role not in ('admin', 'member', 'viewer') then
    raise exception using errcode = '22023', message = 'Invalid membership role';
  end if;
  if actor_role = 'admin' and target_role = 'admin' then
    raise exception using errcode = '42501', message = 'Only the owner can grant admin';
  end if;

  insert into public.organization_memberships (organization_id, user_id, role)
  values (target_organization_id, target_user_id, target_role)
  returning * into created_membership;
  return created_membership;
end;
$$;

create or replace function public.update_organization_member_role(
  target_organization_id uuid,
  target_user_id uuid,
  target_role text
)
returns public.organization_memberships
language plpgsql
security definer
set search_path = public
as $$
declare
  actor_role text;
  previous_role text;
  updated_membership public.organization_memberships;
begin
  select role into actor_role from public.organization_memberships
  where organization_id = target_organization_id and user_id = (select auth.uid());
  select role into previous_role from public.organization_memberships
  where organization_id = target_organization_id and user_id = target_user_id;

  if actor_role is null or actor_role not in ('owner', 'admin') then
    raise exception using errcode = '42501', message = 'Insufficient organization permissions';
  end if;
  if previous_role is null or previous_role = 'owner' or target_role not in ('admin', 'member', 'viewer') then
    raise exception using errcode = '22023', message = 'Invalid membership role transition';
  end if;
  if actor_role = 'admin' and (previous_role = 'admin' or target_role = 'admin') then
    raise exception using errcode = '42501', message = 'Only the owner can manage admin roles';
  end if;
  if target_user_id = (select auth.uid()) then
    raise exception using errcode = '42501', message = 'Users cannot change their own role';
  end if;

  update public.organization_memberships
  set role = target_role
  where organization_id = target_organization_id and user_id = target_user_id
  returning * into updated_membership;
  return updated_membership;
end;
$$;

create or replace function public.remove_organization_member(
  target_organization_id uuid,
  target_user_id uuid
)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  actor_role text;
  target_role text;
begin
  select role into actor_role from public.organization_memberships
  where organization_id = target_organization_id and user_id = (select auth.uid());
  select role into target_role from public.organization_memberships
  where organization_id = target_organization_id and user_id = target_user_id;

  if actor_role is null or actor_role not in ('owner', 'admin') then
    raise exception using errcode = '42501', message = 'Insufficient organization permissions';
  end if;
  if target_role is null or target_role = 'owner' or target_user_id = (select auth.uid()) then
    raise exception using errcode = '42501', message = 'Owner and self-removal are protected';
  end if;
  if actor_role = 'admin' and target_role = 'admin' then
    raise exception using errcode = '42501', message = 'Only the owner can remove an admin';
  end if;

  delete from public.organization_memberships
  where organization_id = target_organization_id and user_id = target_user_id;
end;
$$;

create or replace function public.transfer_organization_ownership(
  target_organization_id uuid,
  new_owner_user_id uuid
)
returns public.organization_memberships
language plpgsql
security definer
set search_path = public
as $$
declare
  actor_role text;
  target_role text;
  transferred_membership public.organization_memberships;
begin
  select role into actor_role from public.organization_memberships
  where organization_id = target_organization_id and user_id = (select auth.uid());
  select role into target_role from public.organization_memberships
  where organization_id = target_organization_id and user_id = new_owner_user_id;

  if actor_role is distinct from 'owner' then
    raise exception using errcode = '42501', message = 'Only the owner can transfer ownership';
  end if;
  if target_role is null or new_owner_user_id = (select auth.uid()) then
    raise exception using errcode = '22023', message = 'New owner must be another existing member';
  end if;

  update public.organization_memberships
  set role = 'admin'
  where organization_id = target_organization_id and user_id = (select auth.uid());
  update public.organization_memberships
  set role = 'owner'
  where organization_id = target_organization_id and user_id = new_owner_user_id
  returning * into transferred_membership;
  return transferred_membership;
end;
$$;

revoke all on function public.add_organization_member(uuid, uuid, text) from public;
revoke all on function public.update_organization_member_role(uuid, uuid, text) from public;
revoke all on function public.remove_organization_member(uuid, uuid) from public;
revoke all on function public.transfer_organization_ownership(uuid, uuid) from public;
grant execute on function public.add_organization_member(uuid, uuid, text) to authenticated;
grant execute on function public.update_organization_member_role(uuid, uuid, text) to authenticated;
grant execute on function public.remove_organization_member(uuid, uuid) to authenticated;
grant execute on function public.transfer_organization_ownership(uuid, uuid) to authenticated;
