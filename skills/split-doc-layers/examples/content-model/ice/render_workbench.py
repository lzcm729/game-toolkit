"""Render the reviewed YAML snapshot; this is not an engine data importer."""
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"   # examples/content-model/ice → split-doc-layers/scripts
sys.path.insert(0, str(SCRIPTS))
from check_content_model import load_model, validate  # noqa: E402


def render(model):
    errors = validate(model)
    if errors:
        raise ValueError("\n".join(errors))
    sources = {s["id"]: s for s in model["sources"]}
    instance = model["instances"][0]
    out = [
        "# ice 作者工作台（真实只读样板）", "",
        "本文件由同目录 render_workbench.py 从 ice.content.yaml **生成**，勿独立手改。"
        "YAML 是人工核对源码后编排的作者快照，未实现自动从引擎提取或回流。",
        "",
        "业务字段逐项标分类；声明性表示可交机械校验，不代表本检查器已核过引擎值。"
        "解释性需语义校验，C 表示 C 层绑定。"
        "固定结构元数据（ID、版本、字段类型、来源定位、生效说明、引用及投影分区）按 schema "
        "归声明性，只校格式和关联；其中自然语言的真伪仍须人工复核。",
        "",
        "证据路径相对奶茶项目根；src.sample 相对插件根。有效值只指固定版本加载配置时的基础值，"
        "未运行 Godot，不涵盖运行时实验覆写、等级、天气或已有 buff 合并后的结果。",
        "",
        "publication_ir 是**候选字段映射声明**，不是已生成的运行资源；"
        "结构通过不代表机制契约完备或允许发布。此样板未改变任何项目文件。",
        "",
        "## 实例身份与定位", "",
        f"- ID（声明性）：{instance['id']}",
        f"- 针对版本（声明性）：{instance['version']}", "",
    ]

    def fields(items):
        for field in items:
            label = "声明性" if field["classification"] == "declarative" else "解释性 · " + field["owner"]
            value = field["value"]
            if isinstance(value, list):
                value = "、".join(str(v) for v in value)
            out.extend([f"**{field['id']}** — {label}", "", str(value), ""])
            out.append(f"- 生效方式：{field['effective']}")
            for sid in field["sources"]:
                source = sources[sid]
                out.append(f"- 来源 {sid}：{source['locator']} @ {source['version']}")
            out.append("")

    fields(instance["identity"])
    out.extend(["## 已采纳定义", "",
                "定义身份及参数与代码解读分开标记；现行代码不自动升级为已采纳机制契约。", ""])
    fields(instance["adopted"]["fields"])
    for branch in instance["adopted"]["branches"]:
        out.extend([f"### 分支 {branch['id']}", ""])
        fields(branch["fields"])
    out.extend(["### 机制引用登记（不补规则）", ""])
    for mechanism in model["mechanisms"]:
        out.extend([f"**{mechanism['id']}** — 状态 {mechanism['status']}（声明性登记）", ""])
        fields(mechanism["fields"])
    out.extend(["### 关系集合（不手抄成员清单）", ""])
    for catalog in model["catalogs"]:
        out.extend([f"集合 ID（声明性）：{catalog['id']}", ""])
        fields(catalog["fields"])
    out.extend(["## 发布情况", ""])
    fields(instance["release"])
    out.extend(["### 作者字段与候选发布字段的边界", "",
                "同一个实例身份；下列目标仅为字段集合草案，不是已接入的导出器。"
                "解释、讨论及兼容残留均被本映射排除。", ""])
    for projection in model["publication_ir"]:
        out.extend([f"声明性映射 {projection['id']} → 实例 {projection['instance_id']}", "",
                    "| 目标字段 ID | 作者字段来源 |", "|---|---|"])
        for target in projection["fields"]:
            out.append(f"| {target['id']} | {', '.join(target['from'])} |")
        out.extend(["", "声明性排除集（其余作者字段必须逐项列入，检查器验证分区）：", ""])
        out.extend(f"- {fid}" for fid in projection["excluded"])
        out.append("")
    out.extend(["## 设计讨论", "", "以下内容未进入正式定义或发布输入；空白“我的意见”不冒充用户观点。", ""])
    for discussion in instance["discussion"]:
        out.extend([f"### {discussion['id']}", "",
                    f"- 绑定对象（声明性）：{discussion['target']}",
                    f"- 针对版本（声明性）：{discussion['target_version']}", ""])
        fields(discussion["fields"])
    return "\n".join(out).rstrip() + "\n"


if __name__ == "__main__":
    folder = Path(__file__).resolve().parent
    model = load_model(folder / "ice.content.yaml")
    (folder / "ice.workbench.md").write_text(render(model), encoding="utf-8")
