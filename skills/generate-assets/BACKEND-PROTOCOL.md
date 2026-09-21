# 生图后端协议

generate-assets 自己不生图。它把 asset 列表翻译成 batch JSON，然后 subprocess
调用一个**后端脚本**。任何满足本协议的可执行 Python 脚本都能当后端 —— 后端
不是 skill，不需要 SKILL.md，Claude 不会单独触发它。

## 调用约定

```
python <backend.py> <batch.json> --output-dir <dir> [--dry-run] [--force]
```

- `--dry-run`：只打印计划，不发请求、不写文件
- `--force`：目标文件已存在时仍重新生成（缺省则计入 skipped）
- 输出目录里的 `.generate-assets.json` 归编排层（生成记录），**后端别读也别写**。
  后端只管「文件在就跳过」；那张图还对不对得上当前配置，由编排层判断

当前实现用 `sys.executable` 拼命令行，因此后端**必须是 Python 脚本**。

## 输入：batch JSON

```json
{
  "$schema_version": 2,
  "defaults": {"aspect_ratio": "1:1", "seed": 123, "reference_paths": ["/abs/anchor.png"]},
  "assets": [{"name": "red_bean", "filename": "red_bean.png", "prompt": "...",
              "model": "gemini-3-pro-image"}]
}
```

- `assets[].name` / `filename` / `prompt` 必有；`aspect_ratio` / `seed` / `model` / `image` 为 item 级，优先于 `defaults`
- `reference_paths` 已是绝对路径，后端不必处理 `res://` 等引擎前缀
- `model` 可出现在 `defaults` 或 asset 上（asset 优先）。后端不认就该告警，别静默换成自己的默认
- **`image`（编辑底图）只在 asset 上，不进 `defaults`** —— 上游 image-gen 的 `Defaults`
  不解析它，放 defaults 会被静默丢掉。它与 `reference_paths` **互斥**：
  `image` 是「编辑这张图」，`reference_paths` 是「参考这些图的风格」
- 后端应校验 `$schema_version`，不认识的版本直接报错，不要猜
- 后端忽略不认识的 `defaults` 字段即可；判断由上层基于能力声明做出。
  **丢掉会改变任务含义的字段（`model` / `chain` / `preset` / `reference_paths` /
  `image` / `aspect_ratio`）默认阻止执行**，不是告警 —— 仍然出得来图，但那不是
  用户要的那件事，而批量是按张烧钱的。要降级得明说（`--allow-degrade`）。
  `seed` 那类只影响可复现性的照旧告警继续。
  **这个保证只覆盖按注册名选中的后端**（`backend: image-gen` / `laozhang`）：
  脚本路径式后端和 `IMAGE_GEN_SCRIPT` 指定的后端，上层无从得知其能力，
  按「**未知**」处理 —— 既不报降级，也不声称查过。这类后端必须自己在丢弃字段时出声
- 能力按模型而非按后端分的字段（例如某些模型没有 `seed`），字段集合式的能力声明
  表达不了。**内置后端**可以在注册表里填 `incompatibilities(defaults, asset)`，
  返回人话消息列表 —— 上层据此在发请求之前报错，校验器也走同一条。
  规则写在后端自己这边，上层不按后端名特判；新增后端只要填这一格。
  脚本路径式后端填不了，必须在丢弃处自己告警
- 目标文件已存在且未给 `--force` 时按 skipped 处理。这一判断应优先于凭证检查 ——
  已经生成好的资源不该因为缺 key 被整批拦住

## 输出：stdout 末行 JSON

```json
{"total": 12, "success": 10, "failed": 1, "skipped": 1}
```

四个字段必需，必须是 stdout 最后一行。可选 `failed_assets` / `manifest`。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 全成功（含全部 skipped） |
| 1 | 全失败 |
| 2 | 部分失败 |

非 dry-run 时若拿不到 summary，上层即便见到退码 0 也判失败。

## 最小骨架

```python
#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("batch")
ap.add_argument("--output-dir", required=True)
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--force", action="store_true")
args = ap.parse_args()

batch = json.loads(Path(args.batch).read_text(encoding="utf-8"))
if batch.get("$schema_version") != 2:
    print(f"[fatal] 不支持的 schema: {batch.get('$schema_version')}", file=sys.stderr)
    sys.exit(1)

out = Path(args.output_dir)
assets = batch.get("assets") or []
success = failed = skipped = 0
for a in assets:
    target = out / a["filename"]
    if args.dry_run:
        print(f"  [plan] {a['name']} -> {target}")
        continue
    if target.exists() and not args.force:
        skipped += 1
        continue
    try:
        target.write_bytes(your_image_api(a["prompt"]))   # 换成你的生图调用
        success += 1
    except Exception as e:
        print(f"  [error] {a['name']}: {e}", file=sys.stderr)
        failed += 1

print(json.dumps({"total": len(assets), "success": success,
                  "failed": failed, "skipped": skipped}))
sys.exit(0 if failed == 0 else (1 if success == 0 and skipped == 0 else 2))
```

## 接上自己的后端

```yaml
backend: tools/my_backend.py    # 相对路径以 project_root 为基准
```

也可以用 `IMAGE_GEN_SCRIPT=<路径>` 环境变量临时覆盖（优先级最高）。

## 内置后端

| 名字 | 脚本 | 说明 |
|---|---|---|
| `image-gen` | `~/.claude/skills/image-gen/scripts/generate_image.py` | 缺省。多 provider、chain fallback、preset、manifest。需单独安装 |
| `laozhang` | 插件内 `scripts/backends/laozhang_backend.py` | 随插件走。单 provider、串行、无 chain/preset |

### laozhang 后端的两条路径

按 `model` 前缀分流，能力不同：

| 模型家族 | API 路径 | 多图 reference | 单图 edit | key |
|---|---|---|---|---|
| `gemini-*` | `/v1beta/...:generateContent` | 支持 | 支持 | `LAOZHANG_API_KEY` |
| `gpt-image-*` | `/v1/images/{generations,edits}` | **不支持** | 支持 | `LAOZHANG_OFFICIAL_API_KEY`（缺则回退上面那把） |

`gpt-image-*` 还有两个限制会被告警而不是静默吞掉：给了 `reference_paths` 直接报错；
`aspect_ratio` 只原生支持 `1:1` / `2:3` / `3:2`，其余就近取一档、边缘被裁。
