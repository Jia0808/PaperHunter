# Repository Safety Checklist

This document records the recommended GitHub settings for protecting the PaperHunter repository from accidental destructive changes.

## What Can and Cannot Be Prevented

For a personal GitHub repository, the account owner can still delete the repository from GitHub's danger zone after confirmation. The practical protection is to reduce who has admin access, protect the default branch, enable account security, and keep backups.

## Recommended GitHub Settings

1. Keep the repository under one trusted owner account.
2. Do not grant `Admin` access to collaborators unless absolutely necessary.
3. Enable two-factor authentication on the owner account.
4. Save GitHub recovery codes offline.
5. Protect the default branch, usually `main`.
6. Require pull requests before merging into `main` once there are collaborators.
7. Block force pushes on `main`.
8. Block branch deletion for `main`.
9. Require status checks once CI is enabled.
10. Keep at least one local clone and one remote backup.

## Suggested Branch Rule

Create a branch protection rule or repository ruleset for:

```text
main
```

Recommended protections:

- disallow force pushes
- disallow deletions
- require pull request before merge
- require at least one approval when collaborators exist
- require CI to pass before merge

## Backup Commands

After the repository is pushed, keep a local mirror backup:

```bash
git clone --mirror https://github.com/Jia0808/PaperHunter.git PaperHunter.git
```

Update the mirror backup periodically:

```bash
cd PaperHunter.git
git remote update --prune
```

## Release Tags

Create tags for important stable versions:

```bash
git tag -a v0.1.0 -m "PaperHunter v0.1.0"
git push origin v0.1.0
```

Tags make it easier to recover a known good version even if the main branch changes.

## GitHub References

- Repository rulesets: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
- Creating repository rulesets: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
- Available rules, including deletion and force-push restrictions: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
