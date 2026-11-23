/* eslint-disable i18next/no-literal-string -- Cortex admin surface is English-only until translations land; Canvas UI stays localized. */
import { useState, type FormEvent } from "react";
import { describeCortexError } from "#/api/cortex/cortex-api";
import {
  useInstallations,
  useLinkInstallation,
  useRepositories,
} from "#/api/cortex/cortex-hooks";
import { useCortexWorkspace } from "#/components/features/cortex/cortex-workspace";
import {
  CortexButton,
  CortexCard,
  CortexInput,
  CortexLabel,
  CortexState,
} from "#/components/features/cortex/cortex-ui";

export default function CortexIntegrations() {
  const { activeOrgId } = useCortexWorkspace();
  const installations = useInstallations(activeOrgId);
  const link = useLinkInstallation(activeOrgId);
  const [installationId, setInstallationId] = useState("");
  const [showRepositories, setShowRepositories] = useState(false);
  const repositories = useRepositories(activeOrgId, showRepositories);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = Number(installationId);
    if (!Number.isInteger(value) || value <= 0) return;
    link.mutate(value, { onSuccess: () => setInstallationId("") });
  };

  if (!activeOrgId) {
    return (
      <p className="text-sm text-tertiary-light">{"No organization yet"}</p>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <CortexCard title={"GitHub installations"}>
        <CortexState
          isLoading={installations.isLoading}
          error={installations.error}
          isEmpty={installations.data?.length === 0}
          emptyLabel={"No GitHub installation linked"}
        >
          <ul className="divide-y divide-border text-sm">
            {installations.data?.map((installation) => (
              <li
                key={installation.id}
                className="flex flex-wrap items-center justify-between gap-2 py-2"
              >
                <span>
                  <span className="text-content">
                    {installation.account_login}
                  </span>
                  <span className="ml-2 text-xs text-tertiary-light">
                    #{installation.installation_id} · {installation.status}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </CortexState>
      </CortexCard>

      <CortexCard title={"Link installation"}>
        <form className="flex flex-wrap items-end gap-2" onSubmit={submit}>
          <label className="min-w-48 flex-1">
            <CortexLabel>{"Installation id"}</CortexLabel>
            <CortexInput
              type="number"
              min={1}
              required
              value={installationId}
              onChange={(event) => setInstallationId(event.target.value)}
            />
          </label>
          <CortexButton type="submit" disabled={link.isPending}>
            {"Link installation"}
          </CortexButton>
        </form>
        {link.error && (
          <p className="mt-2 text-sm text-danger">
            {describeCortexError(link.error)}
          </p>
        )}
      </CortexCard>

      <CortexCard
        title={"Repositories"}
        actions={
          <CortexButton
            variant="secondary"
            onClick={() => setShowRepositories(true)}
          >
            {"Load repositories"}
          </CortexButton>
        }
      >
        {showRepositories ? (
          <CortexState
            isLoading={repositories.isLoading}
            error={repositories.error}
            isEmpty={repositories.data?.length === 0}
            emptyLabel={"No repositories found"}
          >
            <ul className="divide-y divide-border text-sm">
              {repositories.data?.map((repository) => (
                <li key={repository.id} className="flex justify-between py-2">
                  <span>{repository.full_name}</span>
                  <span className="text-xs text-tertiary-light">
                    {repository.default_branch ?? "-"}
                  </span>
                </li>
              ))}
            </ul>
          </CortexState>
        ) : (
          <p className="text-sm text-tertiary-light">{"None"}</p>
        )}
      </CortexCard>
    </div>
  );
}
