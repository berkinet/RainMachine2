# Release notes

## 1.0.3 — 2026-08-30

### Fixed

- Catch RainMachine API request failures inside each controller refresh instead
  of allowing them to terminate Indigo's concurrent plugin thread.
- Preserve last-known watering, program, remaining-time, and flowmeter states
  while a controller is temporarily unavailable.
- Log one concise unavailable message per outage, retry after 10 seconds, and
  publish one recovery message when communication resumes.
- Fetch a complete status snapshot before publishing it and keep active-zone
  accounting independent for each configured controller.
- Add a final unexpected-error boundary so the concurrent polling thread keeps
  running even if a non-communication polling defect occurs.
