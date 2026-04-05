# New Valdi Project

**Trigger**: `/new-valdi [project-name]`

**Description**: Creates a new Valdi cross-platform application project

---

When this skill is invoked:

1. Extract project name from args, or ask if not provided

2. Ask what type of Valdi project:
   - Full Application (iOS + Android)
   - iOS Only
   - Android Only
   - Library/Module (for embedding in existing apps)

3. Ask for bundle identifiers:
   - iOS bundle ID (e.g., com.example.myapp)
   - Android package name (e.g., com.example.myapp)

4. Create project directory: `mkdir {project-name} && cd {project-name}`

5. Initialize with Valdi CLI:
   ```bash
   valdi bootstrap
   ```

6. If Valdi CLI is not installed, install it first:
   ```bash
   pnpm install -g @snap/valdi
   valdi dev_setup
   ```

7. Initialize git repository:
    ```bash
    git init
    git add .
    git commit -m "chore: initial Valdi project setup"
    ```

8. Print next steps:
    ```
    Project created successfully!

    Next steps:
    1. cd {project-name}
    2. valdi install ios    # Install iOS dependencies
       OR
       valdi install android # Install Android dependencies
    3. valdi hotreload       # Start development with hot reload
    4. Open in VSCode/Cursor and install Valdi extensions

    Useful commands:
    - valdi doctor          # Check environment health
    - valdi projectsync     # Sync after changing deps/resources
    - bazel build //:app    # Build the application

    Documentation: https://github.com/Snapchat/Valdi
    ```

**Example usage**:
- `/new-valdi my-app`
- `/new-valdi` (will prompt for name)
