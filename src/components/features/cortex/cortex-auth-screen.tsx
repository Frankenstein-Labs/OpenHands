/* eslint-disable i18next/no-literal-string -- Cortex admin surface is English-only until translations land; Canvas UI stays localized. */
import { useState } from "react";
import { describeCortexError, signIn, signUp } from "#/api/cortex/cortex-api";
import {
  CortexButton,
  CortexCard,
  CortexInput,
  CortexLabel,
} from "./cortex-ui";

export function CortexAuthScreen() {
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (mode === "sign-in") {
        await signIn(email, password);
      } else {
        await signUp(email, password);
        setNotice("Check your email to confirm the account.");
      }
    } catch (cause) {
      setError(describeCortexError(cause));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-full items-center justify-center p-6">
      <div className="w-full max-w-md">
        <CortexCard title={"Title"}>
          <p className="mb-4 text-sm text-tertiary-light">
            {"AI workspace, models, usage and integrations"}
          </p>
          <form className="space-y-3" onSubmit={submit}>
            <label className="block">
              <CortexLabel>{"Email"}</CortexLabel>
              <CortexInput
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="block">
              <CortexLabel>{"Password"}</CortexLabel>
              <CortexInput
                type="password"
                autoComplete={
                  mode === "sign-in" ? "current-password" : "new-password"
                }
                required
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {error && <p className="text-sm text-danger">{error}</p>}
            {notice && <p className="text-sm text-status-success">{notice}</p>}
            <CortexButton type="submit" disabled={busy} className="w-full">
              {mode === "sign-in" ? "Sign in" : "Create account"}
            </CortexButton>
          </form>
          <button
            type="button"
            className="mt-3 text-sm underline"
            onClick={() =>
              setMode((current) =>
                current === "sign-in" ? "sign-up" : "sign-in",
              )
            }
          >
            {mode === "sign-in"
              ? "Need an account? Create one"
              : "Already have an account? Sign in"}
          </button>
        </CortexCard>
      </div>
    </div>
  );
}
