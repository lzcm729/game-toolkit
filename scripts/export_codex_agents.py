#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把插件的 agents/*.md 导出成 Codex 的自定义 agent：<项目根>/.codex/agents/<name>.toml。

    python export_codex_agents.py <项目根> [--agents-dir <插件 agents 目录>] [--dry-run]

Codex 的自定义 agent 是 TOML（name / description / developer_instructions），放在项目的
`.codex/agents/` 或用户的 `~/.codex/agents/`，插件清单带不进去；这个脚本把四个角色落到
项目仓库里，可随项目提交，同事 pull 下来就有。重新跑会覆盖同名文件 —— 别手改生成物，
改源 agents/*.md 再导。

导出规则：
- description：去掉 Claude 风格的 <example> 块，其余逐行保留（Codex 把它当「何时用」的说明）
- developer_instructions：一段「运行在 Codex 上」的前言 + 源文件正文原样
- 源文件 frontmatter 里的 tools 白名单 Codex 没有对应字段，不导出；model / color 同样忽略
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import tomllib
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
DEFAULT_AGENTS = PLUGIN_ROOT / "agents"
FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
EXAMPLE = re.compile(r"<example>.*?</example>", re.S)

PREAMBLE = (
    "【运行在 Codex 上的说明】下文是为 Claude Code 写的角色指令，照做，只把工具名换成你的等价物："
    "Skill 工具对应你的 skill 机制（名字形如 game-toolkit:xxx）；AskUserQuestion 对应向用户提问；"
    "Read / Write / Edit / Grep / Glob / Bash 对应你的文件与命令工具；"
    "SendMessage / TaskUpdate / TaskGet / TaskList 是 Claude Code 的团队协作工具，你没有就跳过，"
    "把要说的话写进最终结果。\n\n"
)


def plugin_version() -> str:
    for rel in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
        p = PLUGIN_ROOT / rel
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8")).get("version", "unknown")
            except ValueError:
                pass
    return "unknown"


def parse_agent(path: Path) -> dict:
    """读一个 agents/*.md：frontmatter 的 name / description + 正文。坏了就抛 ValueError。"""
    text = path.read_text(encoding="utf-8")
    m = FRONT.match(text)
    if not m:
        raise ValueError("%s：没有 frontmatter（文件要以 --- 开头）" % path.name)
    if yaml is None:
        raise ValueError("需要 PyYAML 解析 frontmatter：pip install pyyaml")
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValueError("%s：frontmatter 不是合法 YAML：%s" % (path.name, exc))
    name = meta.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("%s：frontmatter 缺 name" % path.name)
    desc = meta.get("description")
    if not isinstance(desc, str) or not desc.strip():
        raise ValueError("%s：frontmatter 缺 description" % path.name)
    desc = EXAMPLE.sub("", desc)
    desc = "\n".join(line.strip() for line in desc.splitlines() if line.strip())
    body = text[m.end():]
    return {"name": name.strip(), "description": desc, "body": body, "source": path}


def toml_multiline(s: str) -> str:
    """TOML 多行基本字符串。反斜杠和三引号要转义；结尾紧贴定界符的引号也转义掉。"""
    s = s.replace("\r", "").replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    if s.endswith('"'):
        s = s[:-1] + '\\"'
    return '"""\n' + s + '"""'


def render(agent: dict, version: str, today: str) -> str:
    instructions = PREAMBLE + agent["body"]
    text = (
        "# 由 game-toolkit 的 scripts/export_codex_agents.py 生成（插件 %s，%s）。\n"
        "# 源：agents/%s。别手改这个文件 —— 改源文件再重新导出，重新导出会覆盖。\n"
        "# 源文件的 tools 白名单 Codex 没有对应字段，未导出；沙箱与模型沿用父代理。\n"
        "name = %s\n"
        "description = %s\n"
        "developer_instructions = %s\n"
        % (version, today, agent["source"].name, json.dumps(agent["name"], ensure_ascii=False),
           toml_multiline(agent["description"]), toml_multiline(instructions))
    )
    # 自检：写出去的必须能被 TOML 解析器原样读回
    back = tomllib.loads(text)
    if back["name"] != agent["name"] or back["description"] != agent["description"] \
            or back["developer_instructions"] != instructions:
        raise ValueError("%s：TOML 往返对不上，转义有漏" % agent["source"].name)
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="agents/*.md → <项目根>/.codex/agents/*.toml")
    ap.add_argument("root", help="项目根（.codex/agents 会建在这里）")
    ap.add_argument("--agents-dir", default=str(DEFAULT_AGENTS), help="插件的 agents 目录")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print("项目根不存在：%s" % root, file=sys.stderr)
        return 1
    agents_dir = Path(args.agents_dir)
    sources = sorted(agents_dir.glob("*.md"))
    if not sources:
        print("agents 目录里没有 .md：%s" % agents_dir, file=sys.stderr)
        return 1

    version, today = plugin_version(), dt.date.today().isoformat()
    rendered, errors = [], []
    for src in sources:
        try:
            agent = parse_agent(src)
            rendered.append((agent["name"], render(agent, version, today)))
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        print("有源文件读不了，一个都没写：\n  - " + "\n  - ".join(errors), file=sys.stderr)
        return 1

    out_dir = root / ".codex" / "agents"
    names = ", ".join(n for n, _ in rendered)
    if args.dry_run:
        print("（dry-run）会写 %d 个 agent 到 %s：%s" % (len(rendered), out_dir, names))
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in rendered:
        (out_dir / (name + ".toml")).write_text(text, encoding="utf-8")
    print("已导出 %d 个 agent 到 %s：%s。Codex 开新会话生效；可随项目仓库提交。"
          % (len(rendered), out_dir, names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
