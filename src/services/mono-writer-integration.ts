export interface MonoWriterProposal {
  id: string;
  baseCommit: string;
  commitSha: string;
  changedPaths: string[];
  allowedPathPrefixes?: string[];
}

export interface MonoWriterResult {
  proposalId: string;
  fencingToken: number;
  canonicalCommit: string;
}

export type MonoWriterIntegrator = (
  proposal: MonoWriterProposal,
  fencingToken: number,
) => Promise<string>;

export class MonoWriterError extends Error {}

/**
 * Serializes child proposals before they can touch the canonical branch.
 *
 * This coordinator deliberately does not run git commands itself: the parent
 * integrator supplies the real commit/rebase/test/publish callback. The class
 * enforces the protocol boundary around that callback so only one proposal is
 * active, stale bases are rejected, duplicate commits are idempotent, and
 * overlapping or forbidden paths never reach the writer.
 */
export class MonoWriterIntegrationQueue {
  private tail: Promise<unknown> = Promise.resolve();
  private fencingToken = 0;
  private canonicalCommit: string;
  private readonly integratedCommits = new Set<string>();
  private readonly inFlightPaths = new Set<string>();

  constructor(
    canonicalCommit: string,
    private readonly defaultAllowedPathPrefixes: string[] = [],
  ) {
    this.canonicalCommit = canonicalCommit;
  }

  get head(): string {
    return this.canonicalCommit;
  }

  get nextFencingToken(): number {
    return this.fencingToken + 1;
  }

  enqueue(
    proposal: MonoWriterProposal,
    integrate: MonoWriterIntegrator,
  ): Promise<MonoWriterResult> {
    const run = this.tail.then(async () => {
      this.validate(proposal);
      const token = ++this.fencingToken;
      for (const path of proposal.changedPaths) this.inFlightPaths.add(path);
      try {
        const nextCommit = await integrate(proposal, token);
        if (!nextCommit) {
          throw new MonoWriterError(
            `Integrator returned no canonical commit for proposal ${proposal.id}.`,
          );
        }
        this.canonicalCommit = nextCommit;
        this.integratedCommits.add(proposal.commitSha);
        return {
          proposalId: proposal.id,
          fencingToken: token,
          canonicalCommit: nextCommit,
        };
      } finally {
        for (const path of proposal.changedPaths)
          this.inFlightPaths.delete(path);
      }
    });

    // Keep the queue usable after a failed proposal while preserving the
    // rejection for the caller that submitted it.
    this.tail = run.catch(() => undefined);
    return run;
  }

  private validate(proposal: MonoWriterProposal): void {
    if (this.integratedCommits.has(proposal.commitSha)) {
      throw new MonoWriterError(
        `Proposal ${proposal.id} is already integrated (${proposal.commitSha}).`,
      );
    }
    if (proposal.baseCommit !== this.canonicalCommit) {
      throw new MonoWriterError(
        `Proposal ${proposal.id} is stale: base ${proposal.baseCommit} does not match canonical ${this.canonicalCommit}.`,
      );
    }
    const paths = [...new Set(proposal.changedPaths)];
    if (paths.length !== proposal.changedPaths.length) {
      throw new MonoWriterError(
        `Proposal ${proposal.id} contains duplicate paths.`,
      );
    }
    const allowed =
      proposal.allowedPathPrefixes ?? this.defaultAllowedPathPrefixes;
    if (
      allowed.length > 0 &&
      paths.some(
        (path) =>
          !allowed.some(
            (prefix) => path === prefix || path.startsWith(`${prefix}/`),
          ),
      )
    ) {
      throw new MonoWriterError(
        `Proposal ${proposal.id} changes a forbidden path.`,
      );
    }
    if (paths.some((path) => this.inFlightPaths.has(path))) {
      throw new MonoWriterError(
        `Proposal ${proposal.id} overlaps an active writer.`,
      );
    }
  }
}
