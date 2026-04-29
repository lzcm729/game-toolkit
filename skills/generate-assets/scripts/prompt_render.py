"""Prompt 模板渲染 + derived_fields mini DSL（hardcoded helper，不允许 eval/exec）。

Helper 列表（v1）：
  - join(field, sep)   → sep.join(item[field])
  - upper(field)       → str(item[field]).upper()
  - lower(field)       → str(item[field]).lower()
  - title(field)       → str(item[field]).title()

新增 helper 加到 _HELPERS dict 里即可，不开放任意表达式。
"""
from __future__ import annotations

import re
from typing import Any, Callable


# -------------------- mini DSL --------------------

# 形如 join(toppings, ", ")  或  upper(name)
# 函数名 + 一对圆括号 + 逗号分隔参数（参数支持 bareword 字段名 + 引号字面量）
_DSL_RE = re.compile(
    r"""^\s*
        (?P<name>[a-zA-Z_][a-zA-Z0-9_]*)
        \s*\(\s*
        (?P<args>.*?)
        \s*\)\s*$
    """,
    re.VERBOSE,
)

# 单个参数：bareword 字段名 / "double" 字面量 / 'single' 字面量
_ARG_RE = re.compile(
    r"""
        \s*
        (?:
            "(?P<dq>(?:[^"\\]|\\.)*)" |
            '(?P<sq>(?:[^'\\]|\\.)*)' |
            (?P<word>[a-zA-Z_][a-zA-Z0-9_]*)
        )
        \s*(?:,|$)
    """,
    re.VERBOSE,
)


def _parse_dsl(expr: str) -> tuple[str, list[tuple[str, str]]]:
    """解析 DSL 表达式 → (函数名, [(arg_kind, arg_value), ...])。

    arg_kind ∈ {"field", "literal"}
    """
    m = _DSL_RE.match(expr)
    if not m:
        raise ValueError(f"无效的 derived_fields 表达式: {expr!r}")

    name = m.group("name")
    args_str = m.group("args").strip()
    args: list[tuple[str, str]] = []

    if args_str:
        pos = 0
        while pos < len(args_str):
            am = _ARG_RE.match(args_str, pos)
            if not am or am.end() == pos:
                raise ValueError(
                    f"derived_fields 参数解析失败 at pos {pos}: {expr!r}"
                )
            if am.group("dq") is not None:
                args.append(("literal", _unescape(am.group("dq"))))
            elif am.group("sq") is not None:
                args.append(("literal", _unescape(am.group("sq"))))
            else:
                args.append(("field", am.group("word")))
            pos = am.end()

    return name, args


def _unescape(s: str) -> str:
    """处理 \\n / \\t / \\\\ / \\" / \\' 这几个常用转义。"""
    return (
        s.replace(r"\\", "\x00")
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
        .replace(r"\"", '"')
        .replace(r"\'", "'")
        .replace("\x00", "\\")
    )


# -------------------- helpers --------------------

def _h_join(item: dict, args: list[tuple[str, str]]) -> str:
    if len(args) != 2:
        raise ValueError(f"join() 需要 2 个参数（字段, 分隔符），收到 {len(args)}")
    field_kind, field_name = args[0]
    sep_kind, sep = args[1]
    if field_kind != "field":
        raise ValueError("join() 第 1 参数必须是字段名（bareword）")
    if sep_kind != "literal":
        raise ValueError("join() 第 2 参数必须是字符串字面量")
    seq = item.get(field_name)
    if seq is None:
        raise KeyError(f"join(): 字段 {field_name!r} 不存在")
    if not isinstance(seq, (list, tuple)):
        raise ValueError(
            f"join(): 字段 {field_name!r} 必须是 list/tuple，实际 {type(seq).__name__}"
        )
    return sep.join(str(x) for x in seq)


def _h_simple(transform: Callable[[str], str]) -> Callable[[dict, list[tuple[str, str]]], str]:
    def helper(item: dict, args: list[tuple[str, str]]) -> str:
        if len(args) != 1:
            raise ValueError(
                f"helper 需要 1 个字段参数，收到 {len(args)}"
            )
        kind, name = args[0]
        if kind != "field":
            raise ValueError("helper 参数必须是字段名（bareword）")
        if name not in item:
            raise KeyError(f"helper: 字段 {name!r} 不存在")
        return transform(str(item[name]))
    return helper


_HELPERS: dict[str, Callable[[dict, list[tuple[str, str]]], str]] = {
    "join": _h_join,
    "upper": _h_simple(str.upper),
    "lower": _h_simple(str.lower),
    "title": _h_simple(str.title),
}


def list_helpers() -> list[str]:
    """供 examples / 错误提示用。"""
    return sorted(_HELPERS.keys())


# -------------------- 公共 API --------------------

def evaluate_derived(item: dict, derived_spec: dict | None) -> dict:
    """根据 derived_fields spec 把 derived 字段加入 item 副本。

    derived_spec 是 {field_name: dsl_expr}。返回新 dict（不改原 item）。
    """
    if not derived_spec:
        return dict(item)

    out = dict(item)
    for new_field, expr in derived_spec.items():
        if not isinstance(expr, str):
            raise ValueError(
                f"derived_fields[{new_field!r}] 必须是字符串表达式，实际 {type(expr).__name__}"
            )
        name, args = _parse_dsl(expr)
        helper = _HELPERS.get(name)
        if helper is None:
            raise ValueError(
                f"未知 derived_fields helper: {name!r}（可用：{', '.join(list_helpers())}）"
            )
        out[new_field] = helper(out, args)
    return out


def render_template(template: str, item: dict) -> str:
    """str.format 渲染。缺字段抛出带上下文的 KeyError。"""
    if not isinstance(template, str):
        raise ValueError(
            f"prompt_template 必须是字符串，实际 {type(template).__name__}"
        )
    try:
        return template.format(**item)
    except KeyError as e:
        missing = e.args[0] if e.args else "?"
        raise KeyError(
            f"prompt_template 引用了不存在的字段 {{{missing}}}（item.id={item.get('id')!r}）"
        ) from None
    except IndexError as e:
        raise ValueError(
            f"prompt_template 含位置占位符 {{0}} 等，本框架不支持（item.id={item.get('id')!r}）"
        ) from e


def compose_prompt(
    rendered: str,
    *,
    global_prefix: str = "",
    global_suffix: str = "",
    skip_global: bool = False,
) -> str:
    """拼 prefix + rendered + suffix，跳过空字符串。skip_global=True 时只返回 rendered。"""
    if skip_global:
        return rendered.strip()
    parts: list[str] = []
    if global_prefix:
        parts.append(global_prefix.strip())
    if rendered:
        parts.append(rendered.strip())
    if global_suffix:
        parts.append(global_suffix.strip())
    return " ".join(p for p in parts if p)
