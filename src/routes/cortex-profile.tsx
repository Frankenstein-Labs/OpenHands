/* eslint-disable i18next/no-literal-string -- Cortex admin surface is English-only until translations land; Canvas UI stays localized. */
import { useEffect, useState, type FormEvent } from "react";
import { describeCortexError } from "#/api/cortex/cortex-api";
import { useCortexProfile, useUpdateProfile } from "#/api/cortex/cortex-hooks";
import {
  CortexButton,
  CortexCard,
  CortexInput,
  CortexLabel,
  CortexState,
} from "#/components/features/cortex/cortex-ui";

export default function CortexProfile() {
  const profile = useCortexProfile();
  const update = useUpdateProfile();
  const [fullName, setFullName] = useState("");
  const [locale, setLocale] = useState("en");
  const [timezone, setTimezone] = useState("UTC");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!profile.data) return;
    setFullName(profile.data.full_name ?? "");
    setLocale(profile.data.locale);
    setTimezone(profile.data.timezone);
  }, [profile.data]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setSaved(false);
    update.mutate(
      { full_name: fullName, locale, timezone },
      { onSuccess: () => setSaved(true) },
    );
  };

  return (
    <div className="mx-auto max-w-2xl">
      <CortexCard title={"Profile"}>
        <CortexState isLoading={profile.isLoading} error={profile.error}>
          <form className="space-y-3" onSubmit={submit}>
            <label className="block">
              <CortexLabel>{"Full name"}</CortexLabel>
              <CortexInput
                maxLength={160}
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
              />
            </label>
            <label className="block">
              <CortexLabel>{"Language"}</CortexLabel>
              <CortexInput
                maxLength={12}
                value={locale}
                onChange={(event) => setLocale(event.target.value)}
              />
            </label>
            <label className="block">
              <CortexLabel>{"Timezone"}</CortexLabel>
              <CortexInput
                maxLength={64}
                value={timezone}
                onChange={(event) => setTimezone(event.target.value)}
              />
            </label>
            <div className="flex items-center gap-3">
              <CortexButton type="submit" disabled={update.isPending}>
                {"Save"}
              </CortexButton>
              {saved && (
                <span className="text-sm text-status-success">{"Saved"}</span>
              )}
            </div>
            {update.error && (
              <p className="text-sm text-danger">
                {describeCortexError(update.error)}
              </p>
            )}
          </form>
        </CortexState>
      </CortexCard>
    </div>
  );
}
