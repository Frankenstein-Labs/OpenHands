# CI/CD policy

This repository uses GitHub Actions for verification only and Vercel for deployment. The production path is:

```text
agent
  -> branch
  -> pull request
  -> GitHub Actions CI
  -> review
  -> merge
  -> main
  -> Vercel
  -> production
```

## GitHub Actions: CI only

The workflow in `.github/workflows/ci.yml` installs the locked dependencies and runs lint, tests, builds, and package checks. It must not deploy to Vercel or to any production environment. Do not add `vercel deploy`, `npx vercel`, production deployment actions, or Vercel production credentials to this workflow.

The workflow is intentionally limited to read access for repository contents in its normal test job. Any test artifact publication must remain scoped to non-production pull-request evidence and must never update `main` or trigger a production deployment.

## Vercel: CD only

Vercel remains connected to the repository and is the only production deployment system. Configure `main` as the Vercel Production Branch. Pull Requests may receive Vercel Preview Deployments, while a successful merge to `main` can trigger the production deployment through Vercel’s native Git integration.

GitHub Actions and Vercel must not both run a production deployment command. Keeping the Vercel token, organization ID, and project ID out of the CI workflow prevents a test job from acquiring production deployment authority.

## Branch and agent policy

`main` must be protected in the repository settings. Direct pushes are disabled, Pull Requests are required, and the required CI checks must pass before merge. The OpenHands parent and child agents may create branches and isolated worktrees, but they may not push directly to `main`, merge Pull Requests, or trigger production deployment. The mono-writer is the only integration boundary for child proposals; it must integrate through a Pull Request and the normal CI/review process.

Recommended required check names are `test-and-build (ubuntu)` and any additional checks the repository intentionally enables. Optional live E2E checks should remain clearly separated from the required deterministic CI unless their credentials and runtime are guaranteed for every eligible Pull Request.

## Safe changes

Changes to tests, lint, typecheck, and build steps belong in GitHub Actions. Changes to production deployment settings belong in Vercel. If the deployment provider changes later, add a separate, explicitly authorized CD workflow rather than granting deployment permissions to the existing CI workflow.
