# FoodRec — frontend

React 19 + TypeScript + Vite single-page app for the FoodRec recipe recommendation
system. Styling is Tailwind CSS v4 with shadcn/ui primitives; server state is handled
by TanStack Query and HTTP by a typed axios client.

## Requirements

- Node 22 or newer (developed on Node 25)
- npm 11 or newer
- The FoodRec FastAPI backend running on `http://127.0.0.1:8001`

## Setup

```bash
npm install
cp .env.example .env
```

`.env` holds a single variable:

| Variable       | Default                 | Purpose                       |
| -------------- | ----------------------- | ----------------------------- |
| `VITE_API_URL` | `http://127.0.0.1:8001` | Base URL of the backend API   |

If `VITE_API_URL` is missing the client falls back to `http://127.0.0.1:8001`.

## Running

```bash
npm run dev
```

The dev server binds **http://localhost:5180** (`strictPort` is on, so it fails loudly
instead of hopping to another port — the backend's CORS allowlist only contains
`http://localhost:5180` and `http://127.0.0.1:5180`).

Start the backend separately on port **8001** before signing in; the app talks to it
for authentication, recipes and recommendations.

## Scripts

| Script              | What it does                                    |
| ------------------- | ----------------------------------------------- |
| `npm run dev`       | Vite dev server on port 5180                    |
| `npm run build`     | Type-check (`tsc -b`) and build to `dist/`      |
| `npm run preview`   | Serve the production build locally              |
| `npm run lint`      | ESLint over the TypeScript sources              |
| `npm run typecheck` | `tsc --noEmit` for the app project only         |

## Layout

```
src/
  api/            typed API client and one module per backend resource
  components/
    auth/         route guards
    common/       loading and error states
    layout/       app shell, header, page header, auth layout
    ui/           shadcn/ui primitives
  hooks/          TanStack Query hooks
  lib/            tokens-free helpers: auth storage, query client, formatting, filters
  pages/          route components
```

## Theme

Light theme only. All design tokens live on `:root` in `src/index.css`; the brand
tokens (`--match`, `--star`, `--lime`) are exposed through `@theme inline`, so
`bg-match`, `text-match`, `text-star` and `bg-lime` are available as utilities.
The `dark` variant is bound to a `.dark` ancestor that is never rendered, which keeps
shadcn's `dark:` utilities inert.

Adding another shadcn component:

```bash
npx shadcn@latest add <component>
```

The CLI resolves the `@/*` alias through the `compilerOptions.paths` entry in the root
`tsconfig.json`; `tsconfig.app.json` intentionally declares `paths` without `baseUrl`.
