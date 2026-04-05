---
name: book-to-reference
description: >
  书籍导入工具：将游戏设计书籍（PDF转换的MD文件）提取为结构化参考文件。
  触发场景：
  (1) 用户说"导入这本书"、"提取这本书的内容"
  (2) 用户提供书籍MD文件路径并请求整理
  (3) 用户想要将书籍内容添加到参考资料库
  (4) 用户说"把这本书整理成参考文件"
  输入：PDF转换后的MD文件路径。
  输出：按章节/主题组织的参考文件集合。
---

# Book to Reference Skill

将游戏设计书籍内容提取并整理为结构化参考文件的工作流工具。

## 工作流程

### Phase 1: 评估源文件

1. **读取源文件** - 确认MD文件可读取、转换质量
2. **识别书籍信息** - 作者、书名、章节结构
3. **评估内容** - 识别核心章节、关键概念

### Phase 2: 规划参考文件结构

根据书籍内容规划输出结构：

```
references/
├── {author}-{topic1}.md   # 按主题/章节组织
├── {author}-{topic2}.md
└── ...
```

**命名规范:**
- 作者姓氏小写 (如 `sylvester`, `rouse`, `schell`)
- 主题关键词 (如 `experience`, `elegance`, `decisions`)
- 格式: `{author}-{topic}.md`

### Phase 3: 提取核心内容

每个参考文件应包含：

```markdown
# {Topic Name} ({Author Name})

From "{Book Title}"

## Core Concept

{核心概念的一句话定义}

## Key Ideas

{关键概念的结构化摘要}

## Frameworks/Models

{书中的模型、框架、表格}

## Examples

{书中的案例（如有）}

## Key Mantras

{关键引言或口号}
```

**提取原则:**
- **简洁**: 每个文件控制在200-400行
- **结构化**: 使用表格、列表、代码块
- **可操作**: 包含可直接应用的框架
- **引用原文**: 保留关键引言

### Phase 4: 整合到目标Skill（可选）

如果用户指定目标skill，更新该skill的SKILL.md：

1. 在description中添加新书籍信息
2. 在"Detailed References"部分添加新文件链接
3. 在"Quick Reference"部分添加核心概念摘要

## 输入要求

- **源文件**: PDF转换后的MD文件路径
- **输出目录**: 存放参考文件的目录（默认当前skill的references/）

## 质量检查清单

- [ ] 文件命名遵循 `{author}-{topic}.md` 规范
- [ ] 每个文件有清晰的章节结构
- [ ] 核心概念有一句话定义
- [ ] 包含可操作的框架/模型
- [ ] 文件大小适中（200-400行）
- [ ] 无图片依赖（转为文字描述）

## 示例交互

**用户**: "把这本书整理成参考文件：C:\Users\...\book.md"

**Claude 响应**:
1. 读取并评估源文件
2. 报告书籍信息和建议的章节划分
3. 询问用户确认或调整
4. 生成参考文件
5. 报告完成情况

## 参考模板

详见 [references/template.md](references/template.md) 获取参考文件的完整模板。
