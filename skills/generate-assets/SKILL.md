---
name: generate-assets
description: |
  生成游戏图片资源（物品图标、人物头像）。使用 Gemini 3 Pro Image API 生成水彩风格的游戏资源。

  触发场景：
  (1) 用户说"生成图片"、"生成资源"、"生成头像"、"生成图标"
  (2) 用户说"重新生成XX的图片"、"删除并重新生成"
  (3) 用户说"检查图片质量"、"图片有问题"
  (4) 用户说"列出所有资源"、"查看资源清单"
  (5) 用户想要添加新物品或新人物的图片资源
---

# 资源生成技能

使用 Gemini 3 Pro Image API 生成典当行游戏的图片资源。

## 快速使用

```bash
# 生成所有资源
python .claude/skills/generate-assets/scripts/generate_assets.py all

# 生成物品图标
python .claude/skills/generate-assets/scripts/generate_assets.py items

# 生成人物头像
python .claude/skills/generate-assets/scripts/generate_assets.py characters

# 生成特定资源
python .claude/skills/generate-assets/scripts/generate_assets.py items watch
python .claude/skills/generate-assets/scripts/generate_assets.py characters emma

# 列出所有可生成资源
python .claude/skills/generate-assets/scripts/generate_assets.py list
```

按 **Ctrl+C** 可随时中断生成。

## 前置条件

- `.env` 文件中设置 `GEMINI_API_KEY` 或 `NANO_BANANA_API_KEY`
- **无需额外依赖** (脚本只使用 Python 标准库)

## 命令参考

| 命令 | 说明 |
|------|------|
| `items [filter]` | 生成物品图标，可选过滤器 |
| `characters [filter]` | 生成人物头像，可选过滤器 |
| `all` | 生成所有资源 |
| `list` | 列出所有可生成的资源 |
| `manifest` | 只生成资源清单 |

## 重新生成流程

当图片质量不佳需要重新生成时：

```bash
# 1. 手动删除问题图片
rm assets/characters/emma/angry.png

# 2. 重新生成（脚本会跳过已存在的文件）
python .claude/skills/generate-assets/scripts/generate_assets.py characters emma
```

## 输出结构

```
assets/
├── items/<item_id>/
│   ├── default.png
│   ├── restored.png
│   └── reforged.png
├── characters/<char_id>/
│   ├── neutral.png
│   ├── grateful.png
│   ├── resentful.png
│   ├── desperate.png
│   └── angry.png
└── manifest.json
```

## 资源定义

**物品 (16个，每个3种状态):**
watch_01, ring_01, painting_01, vase_01, book_01, watch_gambler, console_student, diamond_mystery, emma_clothes, emma_skincare, emma_laptop, emma_watch, zhao_medal, zhao_cert, lin_watch, susan_bag

**人物 (10个，每个5种表情):**
emma, zhao, lin, susan, generic_male_young, generic_male_middle, generic_male_old, generic_female_young, generic_female_middle, generic_female_old

## 添加新资源

编辑 `scripts/generate_assets.py`:

```python
# 添加物品
ITEMS["new_item"] = {
    "category": "类别",
    "states": {
        "default": ("名称", "English prompt"),
        "restored": ("修复名称", "English prompt"),
        "reforged": ("重铸名称", "English prompt"),
    }
}

# 添加人物
CHARACTERS["new_char"] = {
    "name": "名字",
    "description": "描述",
    "emotions": {
        "neutral": "English prompt",
        "grateful": "English prompt",
        # ...
    }
}
```
