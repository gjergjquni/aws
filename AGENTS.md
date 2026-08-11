# Aegis Swarm

React + Vite + Tailwind CSS application for AI-powered return fraud investigation.

## Development Server

A Vite development server runs on port 8443 (configurable via `PORT`).

- Preview URL: access the running app through the preview panel or `http://localhost:8443`
- Hot reload: changes to source files are reflected immediately

## Project Structure

- `src/main.tsx` — React entrypoint; imports `src/index.css` and mounts `src/App.tsx`
- `src/App.tsx` — Router provider
- `src/routes.tsx` — Application routes
- `src/layouts/` — App shell (sidebar, top bar)
- `src/pages/` — Route-level page components
- `src/components/` — Shared UI components
- `src/features/` — Feature-specific components (when needed)
- `src/hooks/` — Custom React hooks
- `src/services/` — API abstraction layer (synthetic data for MVP)
- `src/types/` — Shared TypeScript types
- `src/data/` — Synthetic seed data
- `src/utils/` — Pure utility functions
- `src/lib/` — Constants and configuration
- `src/index.css` — Global CSS and Tailwind v4 theme
- `vite.config.ts` — Vite configuration with `@` alias for `src`
- `package.json` — Dependencies and scripts

## Dependencies

- Runtime: React 19, React Router 8, Recharts
- Styling: Tailwind CSS v4 via `@tailwindcss/vite`
- Build: Vite 8, TypeScript 5.7

## Styling

Use Tailwind utility classes in JSX. Global theme customization lives in `src/index.css`.

## Code quality

- Use double quotes for strings containing apostrophes
- Export page components as default exports
- Keep business logic in hooks/services, not inline in JSX
