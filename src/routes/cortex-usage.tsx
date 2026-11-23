/* eslint-disable i18next/no-literal-string -- Cortex admin surface is English-only until translations land; Canvas UI stays localized. */
import { useLimits, useUsage } from "#/api/cortex/cortex-hooks";
import { useCortexWorkspace } from "#/components/features/cortex/cortex-workspace";
import {
  CortexCard,
  CortexState,
} from "#/components/features/cortex/cortex-ui";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="text-xs text-tertiary-light">{label}</p>
      <p className="mt-1 text-lg font-semibold text-content">{value}</p>
    </div>
  );
}

export default function CortexUsage() {
  const { activeOrgId } = useCortexWorkspace();
  const usage = useUsage(activeOrgId);
  const limits = useLimits(activeOrgId);

  if (!activeOrgId) {
    return (
      <p className="text-sm text-tertiary-light">{"No organization yet"}</p>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <CortexCard title={"Usage"}>
        <CortexState isLoading={usage.isLoading} error={usage.error}>
          {usage.data && (
            <div className="grid gap-3 sm:grid-cols-3">
              <Metric
                label={"Credit limit"}
                value={usage.data.credits_limit.toFixed(2)}
              />
              <Metric
                label={"Credits used"}
                value={usage.data.credits_used.toFixed(2)}
              />
              <Metric
                label={"Credits remaining"}
                value={usage.data.credits_remaining.toFixed(2)}
              />
            </div>
          )}
        </CortexState>
      </CortexCard>

      <CortexCard title={"Usage by type"}>
        <CortexState
          isLoading={usage.isLoading}
          error={usage.error}
          isEmpty={Object.keys(usage.data?.by_type ?? {}).length === 0}
          emptyLabel={"None"}
        >
          <ul className="divide-y divide-border text-sm">
            {Object.entries(usage.data?.by_type ?? {}).map(([type, value]) => (
              <li key={type} className="flex justify-between py-2">
                <span>{type}</span>
                <span className="font-mono">{value}</span>
              </li>
            ))}
          </ul>
        </CortexState>
      </CortexCard>

      <CortexCard title={"Plan limits"}>
        <CortexState isLoading={limits.isLoading} error={limits.error}>
          <pre className="overflow-x-auto rounded-lg bg-surface-raised p-3 text-xs">
            {JSON.stringify(
              {
                plan: limits.data?.plan_id,
                limits: limits.data?.limits,
              },
              null,
              2,
            )}
          </pre>
        </CortexState>
      </CortexCard>
    </div>
  );
}
