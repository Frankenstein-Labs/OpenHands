/* eslint-disable i18next/no-literal-string -- Cortex admin surface is English-only until translations land; Canvas UI stays localized. */
import { useState, type FormEvent } from "react";
import {
  useCreateOrganization,
  useCortexProfile,
  useUsage,
} from "#/api/cortex/cortex-hooks";
import { useCortexSession } from "#/api/cortex/cortex-api";
import { useCortexWorkspace } from "#/components/features/cortex/cortex-workspace";
import {
  CortexButton,
  CortexCard,
  CortexInput,
  CortexLabel,
  CortexState,
} from "#/components/features/cortex/cortex-ui";

export default function CortexOverview() {
  const session = useCortexSession();
  const profile = useCortexProfile();
  const { organizations, activeOrganization, activeOrgId, role } =
    useCortexWorkspace();
  const usage = useUsage(activeOrgId);
  const createOrganization = useCreateOrganization();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    createOrganization.mutate(
      { name, slug },
      {
        onSuccess: () => {
          setName("");
          setSlug("");
        },
      },
    );
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <CortexCard title={"Profile"}>
        <CortexState isLoading={profile.isLoading} error={profile.error}>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-tertiary-light">{"Full name"}</dt>
              <dd className="text-content">
                {profile.data?.full_name || "None"}
              </dd>
            </div>
            <div>
              <dt className="text-tertiary-light">{"Email"}</dt>
              <dd className="text-content">{session?.email}</dd>
            </div>
          </dl>
        </CortexState>
      </CortexCard>

      {organizations.length === 0 ? (
        <CortexCard title={"No organization yet"}>
          <form className="space-y-3" onSubmit={submit}>
            <label className="block">
              <CortexLabel>{"Name"}</CortexLabel>
              <CortexInput
                required
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label className="block">
              <CortexLabel>{"Slug"}</CortexLabel>
              <CortexInput
                required
                pattern="[a-z0-9][a-z0-9-]{1,62}[a-z0-9]"
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
              />
            </label>
            {createOrganization.error && (
              <p className="text-sm text-danger">
                {String(createOrganization.error)}
              </p>
            )}
            <CortexButton type="submit" disabled={createOrganization.isPending}>
              {"Create organization"}
            </CortexButton>
          </form>
        </CortexCard>
      ) : (
        <CortexCard title={"Usage"}>
          <CortexState isLoading={usage.isLoading} error={usage.error}>
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <p className="text-xs text-tertiary-light">{"Organization"}</p>
                <p className="text-sm text-content">
                  {activeOrganization?.name}
                </p>
              </div>
              <div>
                <p className="text-xs text-tertiary-light">{"Role"}</p>
                <p className="text-sm text-content">{role ?? "None"}</p>
              </div>
              <div>
                <p className="text-xs text-tertiary-light">
                  {"Credits remaining"}
                </p>
                <p className="text-sm text-content">
                  {usage.data ? usage.data.credits_remaining.toFixed(2) : "-"}
                </p>
              </div>
            </div>
          </CortexState>
        </CortexCard>
      )}
    </div>
  );
}
