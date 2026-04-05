# Project Setup

**Trigger**: `/project-setup [project-name]`

**Description**: Initialize a new project with basic tooling and configuration

---

When this skill is invoked:

1. Extract project name from args, or ask if not provided

2. Ask what type of project:
   - Node.js/TypeScript Library
   - Command Line Tool (CLI)
   - Static Website (HTML/CSS/JS)
   - Browser Extension
   - Electron App
   - React Component Library

3. Create project directory and initialize based on type

4. Set up essential tooling:
   - Git initialization
   - .gitignore (based on project type)
   - .editorconfig
   - package.json with appropriate scripts
   - TypeScript configuration (if applicable)

5. Add code quality tools (ask user):
   - ESLint
   - Prettier
   - Husky (git hooks)
   - lint-staged
   - Commitlint

6. Add testing framework (ask user):
   - Jest
   - Vitest
   - Playwright (for E2E)
   - Cypress

7. Create basic project structure:
   - src/ directory
   - tests/ or __tests__/ directory
   - docs/ directory
   - Basic README.md

8. Add CI/CD template (ask user):
   - GitHub Actions
   - GitLab CI
   - None

9. Create LICENSE file (ask which license)

10. Create initial commit with message "chore: initial project setup"

**Example usage**:
- `/project-setup my-library`
- `/project-setup` (will prompt for name)
