import { PrefetchPageLinks, useLocation } from "react-router";
import { HomeChatLauncher } from "#/components/features/home/home-chat-launcher";
import { HomeMobileChrome } from "#/components/features/home/home-mobile-chrome";
import { LlmNotConfiguredBanner } from "#/components/features/home/llm-not-configured-banner";
import {
  isOnboardingPreviewActive,
  OnboardingHost,
} from "#/components/features/onboarding";

<PrefetchPageLinks page="/conversations/:conversationId" />;

function HomeScreen() {
  const location = useLocation();
  const isPreview = isOnboardingPreviewActive(location.search);

  return (
    <div
      data-testid="home-screen"
      className="relative isolate flex h-full flex-col overflow-hidden rounded-xl bg-black text-white md:bg-transparent md:text-foreground"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 z-0 h-2/3 blur-3xl md:hidden"
        style={{
          background:
            "radial-gradient(ellipse at 50% 88%, rgba(255, 51, 102, .92) 0%, rgba(177, 64, 218, .82) 33%, rgba(36, 102, 255, .78) 62%, rgba(5, 6, 10, 0) 100%)",
        }}
      />
      <HomeMobileChrome />

      <div className="custom-scrollbar-always relative z-10 min-h-0 flex-1 overflow-y-auto px-4 pb-28 pt-14 md:px-0 md:pb-0 md:pt-0 lg:px-10.5">
        <div className="md:px-4 lg:px-0">
          <LlmNotConfiguredBanner />
        </div>

        <HomeChatLauncher />

        {!isPreview ? <OnboardingHost /> : null}
      </div>
    </div>
  );
}

export default HomeScreen;
