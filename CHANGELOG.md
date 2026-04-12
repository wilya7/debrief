# Changelog

All notable changes to debrief are documented in this file.

## [1.1.0] - 2026-04-11

### Added
- Initial plugin scaffold with full multi-agent workflow
- Nine skill commands: slide, style, export, save, view, reset, quit, script, handout
- Five agent definitions: consultant, slide-maker, visual-qa, bug-diagnostic, stylist
- PreToolUse hook (check-write-auth) for write authorization enforcement
- PostToolUse hook for automated consistency review after file writes
- Eight presentation archetypes: lab_meeting, conference_talk, seminar, lecture, journal_club, grant_panel, job_talk, custom
- Bundled vendor assets: mermaid.js, rough.js, KaTeX
- Apache-2.0 license with PaperBanana attribution and patent risk disclosure
