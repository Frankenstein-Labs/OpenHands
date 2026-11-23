/* eslint-disable i18next/no-literal-string -- Cortex admin surface is English-only until translations land; Canvas UI stays localized. */
import { useState, type FormEvent } from "react";
import { describeCortexError } from "#/api/cortex/cortex-api";
import {
  useGenerate,
  useModels,
  useProviders,
} from "#/api/cortex/cortex-hooks";
import { useCortexWorkspace } from "#/components/features/cortex/cortex-workspace";
import {
  CortexButton,
  CortexCard,
  CortexLabel,
  CortexState,
  CortexTextarea,
} from "#/components/features/cortex/cortex-ui";

export default function CortexModels() {
  const { activeOrgId } = useCortexWorkspace();
  const providers = useProviders();
  const models = useModels();
  const generate = useGenerate(activeOrgId);
  const availableModels = (models.data ?? []).filter(
    (model) => model.available,
  );
  const [modelId, setModelId] = useState("");
  const [prompt, setPrompt] = useState("");

  const selectedModel = modelId || availableModels[0]?.id || "";

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedModel) return;
    generate.mutate({
      model_id: selectedModel,
      messages: [{ role: "user", content: prompt }],
    });
  };

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <CortexCard title={"Providers"}>
        <CortexState
          isLoading={providers.isLoading}
          error={providers.error}
          isEmpty={providers.data?.length === 0}
          emptyLabel={"None"}
        >
          <ul className="grid gap-2 sm:grid-cols-2">
            {providers.data?.map((provider) => (
              <li
                key={provider.id}
                className="flex items-center justify-between rounded-lg border border-border p-3 text-sm"
              >
                <span>
                  <span className="font-medium text-content">
                    {provider.name}
                  </span>
                  <span className="ml-2 text-xs text-tertiary-light">
                    {provider.kind}
                  </span>
                </span>
                <span
                  className={`rounded px-2 py-0.5 text-xs ${
                    provider.enabled
                      ? "bg-success-soft text-feedback-success"
                      : "bg-surface-raised text-tertiary-light"
                  }`}
                >
                  {provider.enabled ? "Enabled" : "Disabled"}
                </span>
              </li>
            ))}
          </ul>
        </CortexState>
      </CortexCard>

      <CortexCard title={"Model catalogue"}>
        <CortexState
          isLoading={models.isLoading}
          error={models.error}
          isEmpty={models.data?.length === 0}
          emptyLabel={"None"}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-tertiary-light">
                <tr>
                  <th className="py-1 pr-3">{"Model"}</th>
                  <th className="py-1 pr-3">{"Providers"}</th>
                  <th className="py-1 pr-3">{"Role"}</th>
                  <th className="py-1">{"Available"}</th>
                </tr>
              </thead>
              <tbody>
                {models.data?.map((model) => (
                  <tr key={model.id} className="border-t border-border">
                    <td className="py-2 pr-3">
                      <div className="font-medium text-content">
                        {model.display_name}
                      </div>
                      <div className="font-mono text-xs text-tertiary-light">
                        {model.id}
                      </div>
                    </td>
                    <td className="py-2 pr-3">{model.provider_id}</td>
                    <td className="py-2 pr-3">{model.task}</td>
                    <td className="py-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs ${
                          model.available
                            ? "bg-success-soft text-feedback-success"
                            : "bg-surface-raised text-tertiary-light"
                        }`}
                      >
                        {model.available ? "Available" : model.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CortexState>
      </CortexCard>

      <CortexCard title={"Playground"}>
        {availableModels.length === 0 ? (
          <p className="text-sm text-tertiary-light">
            {
              "No model is configured yet. Ask a platform admin to enable a provider and model."
            }
          </p>
        ) : (
          <form className="space-y-3" onSubmit={submit}>
            <label className="block max-w-sm">
              <CortexLabel>{"Model"}</CortexLabel>
              <select
                className="w-full rounded-lg border border-border bg-surface-raised px-2 py-2 text-sm"
                value={selectedModel}
                onChange={(event) => setModelId(event.target.value)}
              >
                {availableModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <CortexLabel>{"Prompt"}</CortexLabel>
              <CortexTextarea
                rows={4}
                required
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
              />
            </label>
            <CortexButton type="submit" disabled={generate.isPending}>
              {"Generate"}
            </CortexButton>
            {generate.error && (
              <p className="text-sm text-danger">
                {describeCortexError(generate.error)}
              </p>
            )}
            {generate.data && (
              <div className="space-y-1 rounded-lg bg-surface-raised p-3">
                <p className="text-xs text-tertiary-light">
                  {"Output"} · {generate.data.model} · {"credits"}:{" "}
                  {generate.data.credits_charged}
                </p>
                <p className="whitespace-pre-wrap text-sm text-content">
                  {generate.data.content}
                </p>
              </div>
            )}
          </form>
        )}
      </CortexCard>
    </div>
  );
}
