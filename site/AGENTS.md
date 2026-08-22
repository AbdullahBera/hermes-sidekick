# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

## Approved Hermes Sidekick direction

- Treat `.context/generated_images/exec-d7bfcd55-0fdb-4b06-912a-d4b4a6d8e7c8.png` as the visual source of truth.
- Keep the landing page monochrome and original to Hermes Sidekick; do not introduce Ramp's lime accent or copy Ramp-specific content.
- Desktop uses the approved split hero: product promise on the left, private messaging preview on the right.
- Mobile stacks the complete messaging preview below the hero CTA.
- GitHub is the only primary conversion; the conversation is demonstrative rather than interactive.
