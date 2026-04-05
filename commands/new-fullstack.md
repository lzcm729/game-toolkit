# New Full-Stack Project

**Trigger**: `/new-fullstack [project-name]`

**Description**: Creates a new full-stack web application with frontend and backend

---

When this skill is invoked:

1. Ask the user which full-stack setup they want:
   - Next.js (App Router + API Routes + TypeScript)
   - T3 Stack (Next.js + tRPC + Prisma + Tailwind)
   - MERN (MongoDB + Express + React + Node)
   - Monorepo (React frontend + Express backend + shared types)
   - Solito (Expo + Next.js + shared navigation - Universal app for web + mobile)

2. Extract the project name from args, or ask if not provided

3. Create the project based on choice:

   **Next.js Full-Stack**:
   - `npx create-next-app@latest {project-name} --typescript --tailwind --app`
   - Add API route examples
   - Set up database connection (ask which: Prisma, MongoDB, PostgreSQL)

   **T3 Stack**:
   - `npm create t3-app@latest {project-name}`
   - Follow T3 setup prompts

   **MERN**:
   - Create root directory with client/ and server/ subdirectories
   - Client: React + Vite + TypeScript
   - Server: Express + TypeScript + MongoDB
   - Set up proxy configuration

   **Monorepo**:
   - Create monorepo structure (separate apps from component libraries):
     ```
     {project-name}/
       apps/
         web/              # Application code (React + Vite)
         api/              # Backend application (Express)
       packages/
         ui/               # Shared component library with Storybook
           src/
             components/
             index.ts
           .storybook/
           package.json
         shared/           # Shared TypeScript types and utilities
           src/
           package.json
       package.json        # Workspace config
     ```
   - Set up npm workspaces or pnpm workspace

   **Solito (Universal App)**:
   - Ask follow-up questions:
     * Package manager? (pnpm recommended, yarn, npm)
     * Include NativeWind? (Tailwind for React Native)
     * Include authentication? (Clerk, Supabase, custom, skip)
     * Include API layer? (tRPC, REST, skip)
     * Include UI library? (Tamagui, React Native Paper, custom, skip)

   - Use Solito starter template:
     ```bash
     npx create-solito-app@latest {project-name}
     ```
     Or create manually if custom setup needed

   - Create monorepo structure:
     ```
     {project-name}/
       apps/
         expo/              # React Native mobile app
           app/             # Expo Router file-system routes
           package.json
           app.json
         next/              # Next.js web app
           app/             # Next.js App Router
           public/
           package.json
           next.config.js
       packages/
         app/               # Shared UI and navigation
           features/        # Feature screens
           components/      # Reusable components
           lib/            # Utilities
           provider/       # Navigation provider
           package.json
         api/              # Shared API client (if selected)
           package.json
       package.json        # Root workspace config
       pnpm-workspace.yaml # or yarn/npm workspace
       turbo.json         # Turborepo config
     ```

   - Configure based on selections:
     * **NativeWind**: Set up Tailwind config, Metro config, Babel plugin
     * **Clerk**: Install @clerk/clerk-expo and @clerk/nextjs, configure providers
     * **Supabase**: Install @supabase/supabase-js, set up client
     * **tRPC**: Configure tRPC client, create example router
     * **Tamagui**: Install and configure Tamagui for universal styling

   - Add example screens:
     * Home screen (apps/expo/app/index.tsx and apps/next/app/page.tsx)
     * Profile screen with navigation
     * Demonstrate shared navigation with solito/link

   - Configure Metro bundler to watch monorepo
   - Set up TypeScript path aliases
   - Create .env.example for both platforms (NEXT_PUBLIC_ and EXPO_PUBLIC_)

   - Add development scripts to root package.json:
     ```json
     {
       "scripts": {
         "dev": "turbo run dev",
         "dev:next": "pnpm --filter next-app dev",
         "dev:expo": "pnpm --filter expo-app start",
         "build": "turbo run build",
         "lint": "turbo run lint",
         "typecheck": "turbo run typecheck"
       }
     }
     ```

   - Create README with:
     * Project structure explanation
     * Setup instructions (pnpm install)
     * How to run web app (cd apps/next && pnpm dev)
     * How to run mobile app (cd apps/expo && pnpm start)
     * Shared code location (packages/app)
     * Platform-specific code guidelines
     * Deployment instructions (Vercel for web, EAS for mobile)

4. Set up database and ORM:
   - Create database schema/models
   - Set up migration scripts
   - Add seed data scripts

5. Create authentication setup:
   - JWT or session-based auth
   - Login/register endpoints
   - Protected routes/middleware

6. Add common configuration:
   - Environment variables (.env.example)
   - CORS configuration
   - Error handling
   - Logging setup

7. **Set up ESLint with Airbnb style guide** (MANDATORY):
   - Install ESLint and Airbnb config:
     ```bash
     npm install -D eslint eslint-config-airbnb eslint-config-airbnb-typescript \
       @typescript-eslint/eslint-plugin @typescript-eslint/parser \
       eslint-plugin-import eslint-plugin-jsx-a11y eslint-plugin-react \
       eslint-plugin-react-hooks
     ```
   - Create `.eslintrc.cjs` (CommonJS for ESLint config only):
     ```javascript
     module.exports = {
       root: true,
       env: { browser: true, es2022: true, node: true },
       extends: [
         'airbnb',
         'airbnb-typescript',
         'airbnb/hooks',
         'plugin:@typescript-eslint/recommended',
       ],
       parser: '@typescript-eslint/parser',
       parserOptions: {
         ecmaVersion: 'latest',
         sourceType: 'module',
         project: './tsconfig.json',
       },
       plugins: ['@typescript-eslint', 'react', 'react-hooks'],
       rules: {
         'react/react-in-jsx-scope': 'off',
         'react/function-component-definition': ['error', {
           namedComponents: 'function-declaration',
           unnamedComponents: 'arrow-function',
         }],
         'import/prefer-default-export': 'off',
       },
     };
     ```

8. **Set up Husky with pre-commit hook** (MANDATORY):
   - Install Husky and lint-staged:
     ```bash
     npm install -D husky lint-staged
     npx husky init
     ```
   - Create `.husky/pre-commit`:
     ```bash
     npx lint-staged
     ```
   - Add to `package.json`:
     ```json
     {
       "lint-staged": {
         "*.{js,jsx,ts,tsx}": ["eslint --fix", "git add"]
       }
     }
     ```

9. **Ensure TypeScript uses ES modules** (MANDATORY):
   - Set `"type": "module"` in `package.json`
   - Configure `tsconfig.json`:
     ```json
     {
       "compilerOptions": {
         "module": "ESNext",
         "moduleResolution": "bundler",
         "target": "ES2022",
         "esModuleInterop": true,
         "allowSyntheticDefaultImports": true
       }
     }
     ```
   - Use `.js` extensions in imports for Node.js code, or configure bundler appropriately

10. **Set up Vitest for testing** (MANDATORY):
    - Install Vitest and testing libraries:
      ```bash
      # For monorepos, install at root or in each package
      npm install -D vitest @vitest/ui @vitest/coverage-v8 \
        @testing-library/react @testing-library/jest-dom jsdom
      ```
    - Create `vitest.config.ts`:
      ```typescript
      import { defineConfig } from 'vitest/config'
      import react from '@vitejs/plugin-react'

      export default defineConfig({
        plugins: [react()],
        test: {
          environment: 'jsdom',
          globals: true,
          setupFiles: ['./src/test/setup.ts'],
          coverage: {
            provider: 'v8',
            reporter: ['text', 'json', 'html'],
          },
        },
      })
      ```
    - Create `src/test/setup.ts`:
      ```typescript
      import '@testing-library/jest-dom'
      ```
    - Add scripts to `package.json`:
      ```json
      {
        "scripts": {
          "test": "vitest",
          "test:ui": "vitest --ui",
          "test:coverage": "vitest run --coverage"
        }
      }
      ```
    - **Monorepo note**: Use `--filter` flag to run tests in specific packages:
      ```bash
      npm run test --workspace=packages/ui
      # or with pnpm
      pnpm --filter @project/ui test
      ```

11. **Set up Storybook for component library** (MANDATORY):
    - Install Storybook in the component library package (e.g., `packages/ui`):
      ```bash
      # Navigate to component library first
      cd packages/ui
      npx storybook@latest init --type react
      ```
    - Configure `.storybook/main.ts`:
      ```typescript
      import type { StorybookConfig } from '@storybook/react-vite'

      const config: StorybookConfig = {
        stories: ['../src/**/*.mdx', '../src/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
        addons: [
          '@storybook/addon-onboarding',
          '@storybook/addon-essentials',
          '@storybook/addon-interactions',
          '@storybook/addon-a11y',
        ],
        framework: {
          name: '@storybook/react-vite',
          options: {},
        },
      }
      export default config
      ```
    - Create story alongside each component:
      ```
      packages/ui/src/components/
        Button/
          Button.tsx
          Button.styles.ts
          Button.stories.tsx
          Button.test.tsx
          index.ts
      ```
    - Example story template (`Button.stories.tsx`):
      ```typescript
      import type { Meta, StoryObj } from '@storybook/react'
      import { Button } from './Button'

      const meta: Meta<typeof Button> = {
        title: 'Components/Button',
        component: Button,
        tags: ['autodocs'],
      }
      export default meta

      type Story = StoryObj<typeof Button>

      export const Primary: Story = {
        args: { variant: 'primary', children: 'Click me' },
      }
      ```
    - Add scripts to component library `package.json`:
      ```json
      {
        "scripts": {
          "storybook": "storybook dev -p 6006",
          "build-storybook": "storybook build"
        }
      }
      ```

12. **Separate application from component library** (MANDATORY):
    - Component library (`packages/ui`):
      * Contains only reusable, presentational components
      * No business logic or API calls
      * Each component has: `.tsx`, `.styles.ts`, `.stories.tsx`, `.test.tsx`
      * Exports components via barrel file (`index.ts`)
    - Application (`apps/web` or `apps/api`):
      * Contains business logic, routing, API integration
      * Imports components from `@project/ui`
      * Feature-based organization for app-specific code
    - Configure workspace dependencies:
      ```json
      // apps/web/package.json
      {
        "dependencies": {
          "@project/ui": "workspace:*",
          "@project/shared": "workspace:*"
        }
      }
      ```

13. Initialize git repository with appropriate .gitignore

14. Create README with:
   - Project structure
   - Setup instructions
   - Development commands
   - Environment variables needed

**Example usage**:
- `/new-fullstack my-saas-app`
- `/new-fullstack` (will prompt for name)

**Note**: For Solito projects, automatically invoke the `solito` skill after project creation to provide specialized guidance for cross-platform development, navigation patterns, and best practices.
