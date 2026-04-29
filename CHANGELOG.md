# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/):
- **Added** for new features
- **Changed** for changes in existing functionality
- **Fixed** for bug fixes
- **Security** for security-related changes
- **Removed** for removed features

## [Unreleased]

## [1.0.0] - 2025-04-29

### Added
- `gamma_generate` — create presentations, documents, webpages, and social posts
- `gamma_get_status` — poll generation progress with optional auto-poll
- `gamma_from_template` — remix existing Gamma templates with variables
- `gamma_list_themes` — browse available visual themes
- `gamma_list_folders` — list Gamma folders
- `gamma_share_email` — share content via email with optional `waitForCompletion`
- `gamma_health` — liveness probe to verify API key and server reachability
- `gamma_archive` — archive a Gamma from the workspace
- Retry with exponential backoff on 429/500/502/503 responses
- Jitter on polling intervals to avoid thundering herd
- `GAMMA_POLL_INTERVAL_MS` and `GAMMA_MAX_POLL_ATTEMPTS` environment variable overrides
- Comprehensive Zod schema validation for all tool inputs
- Input size limits: 50,000 char prompts, 2,000 char headers/footers
- GitHub Actions CI pipeline (build, lint, typecheck, test)
- Vitest test suite with schema validation tests
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue and PR templates
- Dependabot for automated dependency updates

[unreleased]: https://github.com/Arkava-AI/gamma-mcp-server/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Arkava-AI/gamma-mcp-server/releases/tag/v1.0.0
