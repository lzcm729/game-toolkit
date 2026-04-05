# New Website Project

**Trigger**: `/new-website [project-name]`

**Description**: Creates a new modern web development project with your choice of framework

---

When this skill is invoked:

1. Ask the user which framework they want to use:
   - Next.js (App Router with TypeScript)
   - React + Vite (TypeScript)
   - Vue 3 + Vite (TypeScript)
   - Vanilla (HTML/CSS/JS with Vite)

2. Extract the project name from the args, or ask if not provided

3. Create the project in the current directory using the appropriate command:
   - Next.js: `npx create-next-app@latest {project-name} --typescript --tailwind --app --no-src-dir --import-alias "@/*"`
   - React + Vite: `npm create vite@latest {project-name} -- --template react-ts`
   - Vue 3 + Vite: `npm create vite@latest {project-name} -- --template vue-ts`
   - Vanilla: `npm create vite@latest {project-name} -- --template vanilla-ts`

4. Navigate into the project directory

5. Install dependencies: `npm install`

6. Ask if they want to add any common packages:
   - UI Libraries: shadcn/ui, Material-UI, Chakra UI
   - State Management: Zustand, Redux Toolkit, TanStack Query
   - Utilities: axios, date-fns, zod, react-hook-form

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
   - For Vue projects, use `eslint-config-airbnb-base` instead and add `eslint-plugin-vue`

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
         "*.{js,jsx,ts,tsx,vue}": ["eslint --fix", "git add"]
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
    - For Vue projects, use `@testing-library/vue` instead of `@testing-library/react`

11. **Set up Storybook for components** (MANDATORY):
    - Install Storybook:
      ```bash
      npx storybook@latest init --type react
      # For Vue: npx storybook@latest init --type vue3
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
    - Add scripts to `package.json`:
      ```json
      {
        "scripts": {
          "storybook": "storybook dev -p 6006",
          "build-storybook": "storybook build"
        }
      }
      ```

12. **Separate components from application code** (MANDATORY):
    - Create project structure:
      ```
      src/
        components/           # Reusable UI components (with stories)
          Button/
            Button.tsx
            Button.styles.ts
            Button.stories.tsx
            Button.test.tsx
            index.ts
        features/             # Feature-specific code (business logic)
          auth/
          dashboard/
        lib/                  # Utilities and helpers
        hooks/                # Custom hooks
        app/                  # Next.js App Router pages (or pages/ for Vite)
      ```
    - Components folder rules:
      * Only presentational components
      * No business logic or API calls
      * Each component has story and test files
    - Features folder rules:
      * Contains business logic and API integration
      * Can import from components/
      * Feature-specific components live here (not reusable)

13. Initialize git repository if not already initialized

14. Create a basic README with project info and getting started instructions

15. Show the user how to start the dev server

**Example usage**:
- `/new-website my-portfolio`
- `/new-website` (will prompt for name)
