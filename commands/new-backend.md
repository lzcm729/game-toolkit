# New Backend Project

**Trigger**: `/new-backend [project-name]`

**Description**: Creates a new Node.js backend/API project

---

When this skill is invoked:

1. Ask the user which backend setup they want:
   - Express.js + TypeScript
   - Fastify + TypeScript
   - NestJS (opinionated, batteries-included)
   - Hono (lightweight, edge-ready)

2. Extract the project name from args, or ask if not provided

3. Create the project directory: `mkdir {project-name} && cd {project-name}`

4. Initialize the project based on choice:

   **Express.js**:
   - `npm init -y`
   - Install: `npm install express cors dotenv`
   - Install dev: `npm install -D typescript @types/node @types/express @types/cors ts-node-dev nodemon`
   - Create tsconfig.json
   - Create basic Express server with TypeScript

   **Fastify**:
   - `npm init -y`
   - Install: `npm install fastify @fastify/cors dotenv`
   - Install dev: `npm install -D typescript @types/node ts-node-dev`
   - Create tsconfig.json
   - Create basic Fastify server

   **NestJS**:
   - `npx @nestjs/cli new {project-name} --package-manager npm`

   **Hono**:
   - `npm init -y`
   - Install: `npm install hono`
   - Install dev: `npm install -D typescript @types/node tsx`
   - Create basic Hono server

5. Create project structure:
   ```
   src/
     index.ts (or main.ts)
     routes/
     controllers/
     services/
     middleware/
     types/
   ```

6. Add npm scripts to package.json:
   - `dev`: Development server with hot reload
   - `build`: TypeScript compilation
   - `start`: Production server

7. Create `.env.example` with common variables

8. Create `.gitignore` (node_modules, .env, dist)

9. Initialize git repository

10. Ask if they want to add:
    - Database: PostgreSQL (pg), MongoDB (mongoose), Prisma ORM
    - Authentication: JWT setup, Passport.js
    - Validation: Zod, Joi

11. **Set up Vitest for testing** (MANDATORY):
    - Install Vitest and testing libraries:
      ```bash
      npm install -D vitest @vitest/ui @vitest/coverage-v8 supertest @types/supertest
      ```
    - Create `vitest.config.ts`:
      ```typescript
      import { defineConfig } from 'vitest/config'

      export default defineConfig({
        test: {
          globals: true,
          environment: 'node',
          setupFiles: ['./src/test/setup.ts'],
          coverage: {
            provider: 'v8',
            reporter: ['text', 'json', 'html'],
          },
        },
      })
      ```
    - Create `src/test/setup.ts` for global test setup
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
    - **Monorepo note**: If backend is in a monorepo, use workspace filter:
      ```bash
      npm run test --workspace=apps/api
      # or with pnpm
      pnpm --filter @project/api test
      ```
    - Create test structure:
      ```
      src/
        routes/
          users.ts
          users.test.ts      # Route tests
        services/
          userService.ts
          userService.test.ts # Unit tests
        test/
          setup.ts           # Global setup
          fixtures/          # Test data
      ```

12. **Separate layers in backend architecture** (MANDATORY):
    - Create clean architecture structure:
      ```
      src/
        controllers/        # HTTP request handlers (thin, delegate to services)
        services/           # Business logic (testable, no HTTP dependencies)
        repositories/       # Data access layer (database queries)
        middleware/         # Express/Fastify middleware
        routes/             # Route definitions
        types/              # TypeScript types and interfaces
        utils/              # Shared utilities
        test/               # Test setup and fixtures
      ```
    - Layer rules:
      * Controllers: Handle HTTP, validate input, call services
      * Services: Pure business logic, no HTTP or DB dependencies
      * Repositories: Database operations only
    - Each service should have corresponding test file

13. **Set up ESLint with Airbnb style guide** (MANDATORY):
    - Install ESLint and Airbnb config:
      ```bash
      npm install -D eslint eslint-config-airbnb-base eslint-config-airbnb-typescript \
        @typescript-eslint/eslint-plugin @typescript-eslint/parser \
        eslint-plugin-import
      ```
    - Create `.eslintrc.cjs` (CommonJS for ESLint config only):
      ```javascript
      module.exports = {
        root: true,
        env: { es2022: true, node: true },
        extends: [
          'airbnb-base',
          'airbnb-typescript/base',
          'plugin:@typescript-eslint/recommended',
        ],
        parser: '@typescript-eslint/parser',
        parserOptions: {
          ecmaVersion: 'latest',
          sourceType: 'module',
          project: './tsconfig.json',
        },
        plugins: ['@typescript-eslint'],
        rules: {
          'import/prefer-default-export': 'off',
        },
      };
      ```

14. **Set up Husky with pre-commit hook** (MANDATORY):
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
          "*.{js,ts}": ["eslint --fix", "git add"]
        }
      }
      ```

15. **Ensure TypeScript uses ES modules** (MANDATORY):
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

**Example usage**:
- `/new-backend my-api`
- `/new-backend` (will prompt for name)
