-- Corrective migration: invitation acceptance.
-- The invited user accepts with a server-hashed token; the email must match the
-- authenticated user. Runs as SECURITY DEFINER so the invitee does not need write
-- access to memberships.

create or replace function public.accept_organization_invitation(invitation_token_hash text)
returns public.organization_memberships
language plpgsql
security definer
set search_path = public
as $$
declare
  current_user_id uuid := (select auth.uid());
  current_email text;
  target_invitation public.organization_invitations;
  created_membership public.organization_memberships;
begin
  if current_user_id is null then
    raise exception using errcode = '28000', message = 'Authentication required';
  end if;

  select lower(email) into current_email from auth.users where id = current_user_id;

  select * into target_invitation
  from public.organization_invitations
  where token_hash = invitation_token_hash
    and status = 'pending'
    and expires_at > timezone('utc', now())
    and email = current_email
  for update;

  if target_invitation.id is null then
    raise exception using errcode = '22023', message = 'Invitation is invalid or expired';
  end if;

  insert into public.organization_memberships (organization_id, user_id, role)
  values (target_invitation.organization_id, current_user_id, target_invitation.role)
  on conflict (organization_id, user_id) do nothing
  returning * into created_membership;

  update public.organization_invitations
  set status = 'accepted', accepted_by = current_user_id, accepted_at = timezone('utc', now()),
      updated_at = timezone('utc', now())
  where id = target_invitation.id;

  return created_membership;
end;
$$;

revoke all on function public.accept_organization_invitation(text) from public;
grant execute on function public.accept_organization_invitation(text) to authenticated;
