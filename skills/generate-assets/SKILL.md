---
name: generate-assets
description: |
  使用 Gemini API 生成游戏图片资源（物品图标、人物头像、背景图）。
  数据驱动：资源定义从项目配置文件读取，不硬编码。

  触发场景：
  (1) 用户说"生成图片"、"生成资源"、"生成头像"、"生成图标"
  (2) 用户说"重新生成XX的图片"、"删除并重新生成"
  (3) 用户说"列出所有资源"、"查看资源清单"
  (4) 用户想要添加新物品或新人物的图片资源
---

# 资源生成技能

使用 Gemini API 生成游戏图片资源。数据驱动，资源定义从项目配置文件读取。

## 快速使用

```bash
# 脚本位置：plugin 内部
SCRIPT=".claude/skills/generate-assets/scripts/generate_assets.py"

python $SCRIPT items                  # 生成物品图标
python $SCRIPT characters             # 生成人物头像
python $SCRIPT backgrounds            # 生成背景图
python $SCRIPT all                    # 生成所有资源
python $SCRIPT items watch            # 只生成匹配的物品
python $SCRIPT list                   # 列出可生成的资源
python $SCRIPT manifest               # 只生成资源清单
```

按 **Ctrl+C** 可随时中断生成。

## 前置条件

- `.env` 文件中设置 `GEMINI_API_KEY` 或 `NANO_BANANA_API_KEY`
- **无需额外依赖** (脚本只使用 Python 标准库)

## 资源定义（数据驱动）

### 物品（Items）

**数据源：** 项目的物品 CSV（路径从脚本自动发现 `assets/data/Items_Base.csv`，或在 CLAUDE.md 中指定）

**Prompt 定义：** 每个物品的 `assets/items/{item_id}/prompts.json`

```json
{
  "default": "English description of item in default state",
  "restored": "English description of item in restored state",
  "reforged": "English description of item in reforged/legendary state"
}
```

没有 `prompts.json` 的物品会被跳过。

### 人物（Characters）

**数据源：** `assets/characters/characters.json`

```json
{
  "character_id": {
    "name": "显示名称",
    "description": "角色描述",
    "emotions": {
      "neutral": "English prompt for neutral expression",
      "happy": "English prompt for happy expression",
      "angry": "English prompt for angry expression"
    }
  }
}
```

### 背景（Backgrounds）

**数据源：** `assets/backgrounds/backgrounds.json`

```json
{
  "background_id": {
    "name": "显示名称",
    "description": "场景描述",
    "prompt": "English prompt for background generation"
  }
}
```

### 风格定义（可选覆盖）

**默认风格：** 水彩插画风格（内置）

**自定义：** 创建 `assets/style.json` 覆盖默认风格：

```json
{
  "item": {
    "prefix": "Your style prefix for items:",
    "suffix": "Your style constraints for items."
  },
  "character": {
    "prefix": "Your style prefix for portraits:",
    "suffix": "Your style constraints for portraits."
  },
  "background": {
    "prefix": "Your style prefix for backgrounds:",
    "suffix": "Your style constraints for backgrounds."
  }
}
```

## 输出结构

```
assets/
├── items/<item_id>/
│   ├── prompts.json          # prompt 定义（输入）
│   ├── default.png           # 生成的图片（输出）
│   ├── restored.png
│   └── reforged.png
├── characters/
│   ├── characters.json       # 角色定义（输入）
│   └── <char_id>/
│       ├── neutral.png       # 生成的图片（输出）
│       ├── happy.png
│       └── angry.png
├── backgrounds/
│   ├── backgrounds.json      # 背景定义（输入）
│   └── <bg_id>.png           # 生成的图片（输出）
├── style.json                # 风格覆盖（可选输入）
└── manifest.json             # 资源清单（自动生成）
```

## 重新生成流程

```bash
# 1. 删除问题图片
rm assets/characters/hero/angry.png

# 2. 重新生成（脚本跳过已存在的文件）
python $SCRIPT characters hero
```

## 添加新资源

1. **新物品：** 在 CSV 中添加记录 + 创建 `assets/items/{id}/prompts.json`
2. **新人物：** 在 `assets/characters/characters.json` 中添加条目
3. **新背景：** 在 `assets/backgrounds/backgrounds.json` 中添加条目
4. 运行生成命令
