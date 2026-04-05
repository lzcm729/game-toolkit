---
name: package-portable
description: |
  打包项目为 Windows 便携版可执行文件（Electron portable/unpacked directory）。
  触发场景：
  (1) 用户说"打包"、"打包项目"、"生成exe"、"构建可执行文件"、"出包"
  (2) 用户说"发布"、"build portable"、"打个便携版"、"生成便携版"
  (3) 用户想要分发游戏给测试者或玩家
  (4) 用户说"压缩发布"、"打包成zip"
  只生成便携版（unpacked dir），不生成安装包（installer）。
---

# Package Portable

打包当前 React + Electron 项目为 Windows 便携版。

## 打包流程

### 1. 前置检查

确认以下条件，缺失则修复：

- `electron` 和 `electron-builder` 在 devDependencies
- `electron/main.cjs` 存在
- `package.json` 中 `"main"` 指向 `electron/main.cjs`
- `package.json` 的 `build.win.target` 包含 `"dir"`（禁止 nsis）

### 2. 构建

```bash
npm run electron:build
```

### 3. 产物

```
release/win-unpacked/
├── The Pawn's Dilemma.exe
├── resources/app/
└── ...
```

### 4. 分发（可选）

用户要求压缩时，将 `release/win-unpacked/` 压缩为 zip：

```bash
python -c "import shutil; shutil.make_archive('release/ThePawnsDilemma-portable', 'zip', 'release/win-unpacked')"
```

## 注意事项

- `.env` 中的 `GEMINI_API_KEY` 会被 Vite 注入构建产物，确保有值或确认 fallback 可用
- `build.win.signAndEditExecutable` 已设为 `false`，跳过签名
- 构建失败时先单独运行 `npm run build` 排查 Vite 问题
