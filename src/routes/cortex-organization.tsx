/* eslint-disable i18next/no-literal-string -- Cortex admin surface is English-only until translations land; Canvas UI stays localized. */
import { useState, type FormEvent } from "react";
import {
  useInvitations,
  useInviteMember,
  useMembers,
  useRemoveMember,
  useUpdateMemberRole,
} from "#/api/cortex/cortex-hooks";
import { useCortexWorkspace } from "#/components/features/cortex/cortex-workspace";
import {
  CortexButton,
  CortexCard,
  CortexInput,
  CortexLabel,
  CortexState,
} from "#/components/features/cortex/cortex-ui";

const ROLES = ["admin", "member", "viewer"] as const;

export default function CortexOrganization() {
  const { activeOrgId, role } = useCortexWorkspace();
  const members = useMembers(activeOrgId);
  const invitations = useInvitations(activeOrgId);
  const invite = useInviteMember(activeOrgId);
  const updateRole = useUpdateMemberRole(activeOrgId);
  const removeMember = useRemoveMember(activeOrgId);
  const [email, setEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<string>("member");

  const canManage = role === "owner" || role === "admin";

  const submit = (event: FormEvent) => {
    event.preventDefault();
    invite.mutate(
      { email, role: inviteRole },
      { onSuccess: () => setEmail("") },
    );
  };

  if (!activeOrgId) {
    return (
      <p className="text-sm text-tertiary-light">{"No organization yet"}</p>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <CortexCard title={"Members"}>
        <CortexState
          isLoading={members.isLoading}
          error={members.error}
          isEmpty={members.data?.length === 0}
          emptyLabel={"None"}
        >
          <ul className="divide-y divide-border">
            {members.data?.map((member) => (
              <li
                key={member.user_id}
                className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"
              >
                <span className="font-mono text-xs text-content">
                  {member.user_id}
                </span>
                <span className="flex items-center gap-2">
                  {canManage && member.role !== "owner" ? (
                    <select
                      className="rounded-lg border border-border bg-surface-raised px-2 py-1 text-xs"
                      value={member.role}
                      onChange={(event) =>
                        updateRole.mutate({
                          userId: member.user_id,
                          role: event.target.value,
                        })
                      }
                    >
                      {ROLES.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="rounded bg-surface-raised px-2 py-0.5 text-xs">
                      {member.role}
                    </span>
                  )}
                  {canManage && member.role !== "owner" && (
                    <CortexButton
                      variant="danger"
                      onClick={() => removeMember.mutate(member.user_id)}
                    >
                      {"Remove"}
                    </CortexButton>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </CortexState>
      </CortexCard>

      <CortexCard title={"Invite"}>
        {canManage ? (
          <form className="flex flex-wrap items-end gap-2" onSubmit={submit}>
            <label className="min-w-56 flex-1">
              <CortexLabel>{"Email"}</CortexLabel>
              <CortexInput
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label>
              <CortexLabel>{"Role"}</CortexLabel>
              <select
                className="rounded-lg border border-border bg-surface-raised px-2 py-2 text-sm"
                value={inviteRole}
                onChange={(event) => setInviteRole(event.target.value)}
              >
                {ROLES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <CortexButton type="submit" disabled={invite.isPending}>
              {"Invite"}
            </CortexButton>
          </form>
        ) : (
          <p className="text-sm text-tertiary-light">{"None"}</p>
        )}
        {invite.error && (
          <p className="mt-2 text-sm text-danger">{String(invite.error)}</p>
        )}
        {invite.data?.token && (
          <p className="mt-2 break-all rounded bg-surface-raised p-2 text-xs">
            {"Invitation token"}: {invite.data.token}
          </p>
        )}
      </CortexCard>

      <CortexCard title={"Invitations"}>
        <CortexState
          isLoading={invitations.isLoading}
          error={invitations.error}
          isEmpty={invitations.data?.length === 0}
          emptyLabel={"None"}
        >
          <ul className="divide-y divide-border text-sm">
            {invitations.data?.map((invitation) => (
              <li
                key={invitation.id}
                className="flex flex-wrap items-center justify-between gap-2 py-2"
              >
                <span>{invitation.email}</span>
                <span className="flex items-center gap-2 text-xs text-tertiary-light">
                  <span className="rounded bg-surface-raised px-2 py-0.5">
                    {invitation.role}
                  </span>
                  <span>{invitation.status}</span>
                  <span>
                    {"expires"}{" "}
                    {new Date(invitation.expires_at).toLocaleDateString()}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </CortexState>
      </CortexCard>
    </div>
  );
}
