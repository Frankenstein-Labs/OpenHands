import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";

/**
 * Adapted from LibreChat's client/src/components/Chat/Landing.tsx.
 *
 * LibreChat's Landing component depends on its own provider tree and data
 * package, so this keeps the same real interaction pattern (SplitText-style
 * per-grapheme entrance and settled landing state) while using OpenHands'
 * existing translation and component boundaries.
 * See THIRD_PARTY_NOTICES.md.
 */
export function LibreChatLandingTitle() {
  const { t } = useTranslation("openhands");
  const title = t(I18nKey.HOME$WHAT_TO_WORK_ON);
  const subtitle = t(I18nKey.HOME$ENGINEERING_TASKS_SUBHEADER);

  return (
    <div
      className="librechat-landing-copy"
      data-testid="librechat-landing-copy"
    >
      <div className="librechat-landing-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <motion.h1
        className="librechat-landing-title"
        initial="hidden"
        animate="visible"
        variants={{
          hidden: {},
          visible: {
            transition: { staggerChildren: 0.035, delayChildren: 0.08 },
          },
        }}
      >
        {Array.from(title).map((character, index) => (
          <motion.span
            key={`${character}-${index}`}
            variants={{
              hidden: { opacity: 0, y: 18 },
              visible: { opacity: 1, y: 0 },
            }}
            transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
          >
            {character === " " ? "\u00a0" : character}
          </motion.span>
        ))}
      </motion.h1>
      <motion.p
        className="librechat-landing-subtitle"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: 0.4,
          delay: Math.min(title.length * 0.035 + 0.18, 0.9),
        }}
      >
        {subtitle}
      </motion.p>
    </div>
  );
}
