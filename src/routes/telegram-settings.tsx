import React from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { I18nKey } from "#/i18n/declaration";
import { BrandButton } from "#/components/features/settings/brand-button";
import { SettingsInput } from "#/components/features/settings/settings-input";
import { useSearchSecrets } from "#/hooks/query/use-get-secrets";
import {
  displayErrorToast,
  displaySuccessToast,
} from "#/utils/custom-toast-handlers";
import { retrieveAxiosErrorMessage } from "#/utils/retrieve-axios-error-message";
import {
  TELEGRAM_SECRET_NAMES,
  configureTelegramWebhook,
  generateWebhookSecret,
  getTelegramWebhookInfo,
  saveTelegramSecrets,
  validateBotToken,
  type BotTokenStatus,
  type WebhookInfo,
} from "#/api/telegram-settings-service";

function StatusPill({
  tone,
  children,
}: {
  tone: "success" | "error" | "neutral";
  children: React.ReactNode;
}) {
  const tones = {
    success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
    error: "bg-red-500/10 text-red-400 border-red-500/20",
    neutral:
      "bg-[var(--oh-interactive-hover-low)] text-tertiary-light border-[var(--oh-border)]",
  };
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function TelegramSettingsScreen() {
  const { t } = useTranslation("openhands");
  const queryClient = useQueryClient();

  const { data: secrets } = useSearchSecrets();

  const [botToken, setBotToken] = React.useState("");
  const [allowedChatId, setAllowedChatId] = React.useState("");
  const [cloudApiKey, setCloudApiKey] = React.useState("");
  const [webhookUrl, setWebhookUrl] = React.useState(
    () => `${window.location.origin}/api/telegram`,
  );
  const [webhookSecret, setWebhookSecret] = React.useState("");
  const [isValidating, setIsValidating] = React.useState(false);
  const [botStatus, setBotStatus] = React.useState<BotTokenStatus | null>(null);
  const [isSettingWebhook, setIsSettingWebhook] = React.useState(false);
  const [webhookInfo, setWebhookInfo] = React.useState<WebhookInfo | null>(
    null,
  );
  const [isSaving, setIsSaving] = React.useState(false);

  const secretNames = new Set((secrets ?? []).map((secret) => secret.name));
  const botTokenStored = secretNames.has(TELEGRAM_SECRET_NAMES.botToken);
  const webhookSecretStored = secretNames.has(
    TELEGRAM_SECRET_NAMES.webhookSecret,
  );
  const allowedChatIdStored = secretNames.has(
    TELEGRAM_SECRET_NAMES.allowedChatId,
  );
  const cloudApiKeyStored = secretNames.has(TELEGRAM_SECRET_NAMES.cloudApiKey);

  const invalidateSecrets = () => {
    queryClient.invalidateQueries({ queryKey: ["secrets-search"] });
    queryClient.invalidateQueries({ queryKey: ["secrets"] });
  };

  const handleValidateBot = async () => {
    if (!botToken.trim()) {
      setBotStatus({
        ok: false,
        error: t(I18nKey.TELEGRAM$BOT_TOKEN_REQUIRED),
      });
      return;
    }
    setIsValidating(true);
    try {
      const status = await validateBotToken(botToken);
      setBotStatus(status);
    } catch (error) {
      const message = retrieveAxiosErrorMessage(error);
      setBotStatus({ ok: false, error: message || String(error) });
    } finally {
      setIsValidating(false);
    }
  };

  const handleCheckWebhook = async () => {
    if (!botToken.trim()) {
      setBotStatus({
        ok: false,
        error: t(I18nKey.TELEGRAM$BOT_TOKEN_REQUIRED),
      });
      return;
    }
    try {
      setWebhookInfo(await getTelegramWebhookInfo(botToken));
    } catch (error) {
      const message = retrieveAxiosErrorMessage(error);
      setWebhookInfo({ ok: false, error: message || String(error) });
    }
  };

  const handleGenerateSecret = () => {
    setWebhookSecret(generateWebhookSecret());
  };

  const handleSetupWebhook = async () => {
    if (!botToken.trim() || !webhookSecret) {
      setBotStatus({
        ok: false,
        error: t(I18nKey.TELEGRAM$BOT_TOKEN_REQUIRED),
      });
      return;
    }
    setIsSettingWebhook(true);
    try {
      const result = await configureTelegramWebhook({
        token: botToken,
        secret: webhookSecret,
        url: webhookUrl,
      });
      if (!result.ok) {
        setWebhookInfo({ ok: false, error: result.error });
      } else {
        setWebhookInfo({ ok: true, url: result.url });
        displaySuccessToast(t(I18nKey.TELEGRAM$WEBHOOK_SETUP_DONE));
      }
    } catch (error) {
      const message = retrieveAxiosErrorMessage(error);
      setWebhookInfo({ ok: false, error: message || String(error) });
    } finally {
      setIsSettingWebhook(false);
    }
  };

  const handleSaveConnection = async () => {
    setIsSaving(true);
    try {
      await saveTelegramSecrets({
        botToken,
        allowedChatId,
        cloudApiKey,
        webhookSecret,
      });
      invalidateSecrets();
      displaySuccessToast(t(I18nKey.TELEGRAM$CONNECTION_SAVED));
    } catch (error) {
      const message = retrieveAxiosErrorMessage(error);
      displayErrorToast(message || t(I18nKey.ERROR$GENERIC));
    } finally {
      setIsSaving(false);
    }
  };

  const hasStoredSecrets =
    botTokenStored ||
    webhookSecretStored ||
    allowedChatIdStored ||
    cloudApiKeyStored;

  return (
    <div data-testid="telegram-settings-screen" className="flex flex-col gap-8">
      <section className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-lg font-medium text-foreground">
              {t(I18nKey.TELEGRAM$CONNECTION_SECTION)}
            </h3>
            <p className="text-sm leading-5 text-tertiary-light">
              {t(I18nKey.TELEGRAM$CONNECTION_SECTION_DESCRIPTION)}
            </p>
          </div>
          {hasStoredSecrets ? (
            <StatusPill tone="success">
              {t(I18nKey.TELEGRAM$SECRETS_STORED)}
            </StatusPill>
          ) : null}
        </div>

        <div className="flex flex-col gap-6">
          <SettingsInput
            testId="telegram-bot-token-input"
            type="password"
            label={t(I18nKey.TELEGRAM$BOT_TOKEN_LABEL)}
            value={botToken}
            onChange={setBotToken}
            placeholder={t(I18nKey.TELEGRAM$BOT_TOKEN_PLACEHOLDER)}
            className="w-full min-w-0"
          />

          {botStatus ? (
            <div
              data-testid="telegram-bot-status"
              className="flex items-start gap-3"
            >
              <StatusPill tone={botStatus.ok ? "success" : "error"}>
                {botStatus.ok
                  ? t(I18nKey.TELEGRAM$BOT_VALID_OK, {
                      username: botStatus.username,
                    })
                  : t(I18nKey.TELEGRAM$BOT_VALID_ERROR, {
                      message: botStatus.error,
                    })}
              </StatusPill>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            <BrandButton
              testId="validate-bot-token"
              type="button"
              variant="secondary"
              isDisabled={isValidating}
              onClick={handleValidateBot}
            >
              {isValidating
                ? t(I18nKey.TELEGRAM$VALIDATING)
                : t(I18nKey.TELEGRAM$VALIDATE_BOT)}
            </BrandButton>
            <BrandButton
              testId="check-webhook-status"
              type="button"
              variant="tertiary"
              onClick={handleCheckWebhook}
            >
              {t(I18nKey.TELEGRAM$CHECK_WEBHOOK_STATUS)}
            </BrandButton>
          </div>

          <SettingsInput
            testId="telegram-allowed-chat-id-input"
            type="text"
            label={t(I18nKey.TELEGRAM$ALLOWED_CHAT_ID_LABEL)}
            value={allowedChatId}
            onChange={setAllowedChatId}
            placeholder={t(I18nKey.TELEGRAM$ALLOWED_CHAT_ID_PLACEHOLDER)}
            className="w-full min-w-0"
          />

          <SettingsInput
            testId="telegram-cloud-api-key-input"
            type="password"
            label={t(I18nKey.TELEGRAM$CLOUD_API_KEY_LABEL)}
            value={cloudApiKey}
            onChange={setCloudApiKey}
            placeholder={t(I18nKey.TELEGRAM$CLOUD_API_KEY_PLACEHOLDER)}
            className="w-full min-w-0"
          />

          <div className="flex justify-start">
            <BrandButton
              testId="save-telegram-connection"
              type="button"
              variant="primary"
              isDisabled={isSaving}
              onClick={handleSaveConnection}
            >
              {t(I18nKey.TELEGRAM$SAVE_CONNECTION)}
            </BrandButton>
          </div>
        </div>
      </section>

      <section className="space-y-4 border-t border-[var(--oh-border)] pt-6">
        <div className="space-y-1">
          <h3 className="text-lg font-medium text-foreground">
            {t(I18nKey.TELEGRAM$WEBHOOK_SECTION)}
          </h3>
          <p className="text-sm leading-5 text-tertiary-light">
            {t(I18nKey.TELEGRAM$WEBHOOK_SECTION_DESCRIPTION)}
          </p>
        </div>

        <div className="flex flex-col gap-6">
          <SettingsInput
            testId="telegram-webhook-url-input"
            type="url"
            label={t(I18nKey.TELEGRAM$WEBHOOK_URL_LABEL)}
            value={webhookUrl}
            onChange={setWebhookUrl}
            className="w-full min-w-0"
          />

          <SettingsInput
            testId="telegram-webhook-secret-input"
            type="password"
            label={t(I18nKey.TELEGRAM$WEBHOOK_SECRET_LABEL)}
            value={webhookSecret}
            onChange={setWebhookSecret}
            className="w-full min-w-0"
          />

          <div className="flex flex-wrap items-center gap-3">
            <BrandButton
              testId="generate-webhook-secret"
              type="button"
              variant="secondary"
              onClick={handleGenerateSecret}
            >
              {t(I18nKey.TELEGRAM$GENERATE_SECRET)}
            </BrandButton>
            <BrandButton
              testId="setup-telegram-webhook"
              type="button"
              variant="primary"
              isDisabled={isSettingWebhook}
              onClick={handleSetupWebhook}
            >
              {isSettingWebhook
                ? t(I18nKey.TELEGRAM$SETTING_WEBHOOK)
                : t(I18nKey.TELEGRAM$SETUP_WEBHOOK)}
            </BrandButton>
          </div>

          {webhookInfo ? (
            <div
              data-testid="telegram-webhook-status"
              className="flex flex-col gap-2 rounded-lg border border-[var(--oh-border)] bg-[var(--oh-interactive-hover-low)] p-3 text-sm"
            >
              <StatusPill tone="neutral">
                {t(I18nKey.TELEGRAM$WEBHOOK_STATUS)}
              </StatusPill>
              {webhookInfo.ok ? (
                <div className="space-y-1 text-tertiary-light">
                  {webhookInfo.url ? (
                    <p>
                      <span className="font-medium text-foreground">
                        {t(I18nKey.TELEGRAM$WEBHOOK_URL_LABEL_SHORT)}:
                      </span>{" "}
                      {webhookInfo.url}
                    </p>
                  ) : null}
                  {webhookInfo.pendingUpdateCount !== undefined ? (
                    <p>
                      <span className="font-medium text-foreground">
                        {t(I18nKey.TELEGRAM$PENDING_UPDATES)}:
                      </span>{" "}
                      {webhookInfo.pendingUpdateCount}
                    </p>
                  ) : null}
                  {webhookInfo.lastError ? (
                    <p>
                      <span className="font-medium text-foreground">
                        {t(I18nKey.TELEGRAM$LAST_WEBHOOK_ERROR)}:
                      </span>{" "}
                      {webhookInfo.lastError}
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="text-tertiary-light">
                  {t(I18nKey.TELEGRAM$WEBHOOK_INFO_ERROR, {
                    message: webhookInfo.error,
                  })}
                </p>
              )}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

export default TelegramSettingsScreen;
