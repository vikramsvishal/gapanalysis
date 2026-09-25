# CMDB & IS Governance — React UI

Enterprise web UI for the V2 local edition.

## Design goals

- Enterprise portal layout rather than a desktop-tool skin.
- Application shell supports multiple governance products.
- Clear separation between navigation, workspaces, execution state, decisions, exceptions and audit evidence.
- Responsive layout for desktop and tablet.
- React + Vite; Node.js is used as the frontend toolchain.
- Core governance processing remains in Python and V1.4.1 remains the golden engine during migration.

## Run locally

From the repository root:

```bash
cd web
npm install
npm run dev
```

Then open the Vite development URL shown by the terminal.

## Current scope

This first slice is a presentation and interaction shell. Its metrics and sample decision rows are intentionally static until the HTTP/application API is introduced.

The next integration boundary should be:

React UI -> HTTP/API adapter -> V2 ApplicationService -> deterministic governance services -> V1.4.1 compatibility engine

Do not put governance rules in React.
