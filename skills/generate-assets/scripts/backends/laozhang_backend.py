#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""laozhang.ai 极简生图后端 —— generate-assets 的参考实现。

它不是 skill，是一个满足 BACKEND-PROTOCOL.md 的普通 CLI 脚本：
读 batch JSON、逐张生图、把 summary 打到 stdout 末行、按三值退码退出。

刻意不做 image-gen 那套 chain / fallback / preset / manifest —— 那是上游
SDK 的职责。本脚本只求「装了插件就能跑通全流程」。

env（按 CWD 向上的 .env → ~/.env → 进程环境变量 依次查找，与 image-gen 同序）:
  LAOZHANG_API_KEY           gemini-* 模型用
  LAOZHANG_OFFICIAL_API_KEY  gpt-image-* 模型用（缺则回退上面那把）
  LAOZHANG_BASE_URL   可选，缺省 https://api.laozhang.ai
  LAOZHANG_MODEL      可选，缺省 gemini-3.1-flash-image-preview
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

SUPPORTED_SCHEMA = 2
DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_BASE_URL = "https://api.laozhang.ai"
DEFAULT_TIMEOUT_S = 180.0
# Gemini native 路径的参考图上限
MAX_REFERENCES = 14
# laozhang 网关实测会间歇断连（SSLEOFError，curl 同一请求却正常）。
# 「极简」指的是不做 chain/fallback/preset，不是连网络重试都没有。
DEFAULT_RETRIES = 2
# OpenAI 路径只认固定档位的 size，aspect_ratio 得映射过去。
# 没有原生对应的比例取最接近的，代价是渲染端 cover 时轻微裁切。
_ASPECT_TO_SIZE = {
    "1:1": "1024x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "3:2": "1536x1024",
    "2:3": "1024x1536",
    "4:3": "1536x1024",   # 近似 3:2
    "3:4": "1024x1536",   # 近似 2:3
    "4:5": "1024x1536",   # 近似 2:3
}
# gpt-image 系推理慢（image-gen 实测 official 分组 ~4min/张），
# 调用方给的超时太短会被中途切断
_OPENAI_MIN_TIMEOUT_S = 360.0
# OpenAI 端点只原生支持这三档，其余比例都是就近取一档，边缘会被裁掉
_OPENAI_EXACT_RATIOS = frozenset({"1:1", "2:3", "3:2"})
# 向上找 .env 的最大层数，与 image-gen 的 env.py 一致
_MAX_ENV_LEVELS = 10


class _Retryable(RuntimeError):
    """值得再试一次的失败：网络抖动、429、5xx。"""


def _read_env_file(path: Path, key: str) -> str:
    """从 .env 里取一个 key。容忍 export 前缀、引号、注释行。"""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        if not sep or name.strip() != key:
            continue
        return value.strip().strip('"').strip("'")
    return ""


def _find_env_value(key: str) -> str:
    """查 env 值：CWD 向上找 .env → ~/.env → os.environ。

    顺序与 image-gen 的 env.py 一致，包括 .env 优先于进程环境变量这点。
    把 key 放在项目 .env 里是常见做法；只读 os.environ 的话，
    「装了插件设个 key 就能跑」在那种环境里根本不成立。
    """
    current = Path.cwd()
    for _ in range(_MAX_ENV_LEVELS):
        env_file = current / ".env"
        if env_file.exists():
            v = _read_env_file(env_file, key)
            if v:
                return v
        parent = current.parent
        if parent == current:
            break
        current = parent

    home_env = Path.home() / ".env"
    if home_env.exists():
        v = _read_env_file(home_env, key)
        if v:
            return v

    return os.environ.get(key, "")


def _generate_one(
    prompt: str,
    *,
    model: str,
    api_key: str,
    base_url: str,
    aspect_ratio: str,
    seed: "int | None",
    reference_paths: list,
    timeout_s: float,
    image_path: "str | None" = None,
) -> bytes:
    """生成一张图，返回图像字节。失败时对网络抖动 / 429 / 5xx 重试。"""
    last: Exception | None = None
    for attempt in range(DEFAULT_RETRIES + 1):
        try:
            return _request_once(
                prompt, model=model, api_key=api_key, base_url=base_url,
                aspect_ratio=aspect_ratio, seed=seed,
                reference_paths=reference_paths, timeout_s=timeout_s,
                image_path=image_path,
            )
        except _Retryable as e:
            last = e
            if attempt >= DEFAULT_RETRIES:
                break
            delay = 2 ** attempt
            print(f"  [retry] {e}；{delay}s 后重试（第 {attempt + 1}/{DEFAULT_RETRIES} 次）",
                  file=sys.stderr)
            time.sleep(delay)
    raise RuntimeError(str(last))


def _request_once(
    prompt: str,
    *,
    model: str,
    api_key: str,
    base_url: str,
    aspect_ratio: str,
    seed: "int | None",
    reference_paths: list,
    timeout_s: float,
    image_path: "str | None" = None,
) -> bytes:
    """发一次请求，按模型家族分流到两条 API 路径。

    gemini-*    → Gemini native：多图 reference 与单图 edit 都支持
    gpt-image-* → OpenAI style：只有单图 edit，没有多图 reference
    """
    if _is_openai_style(model):
        if reference_paths:
            raise RuntimeError(
                f"{model} 走 OpenAI 路径，不支持多图 reference_paths（风格锚）。"
                "改用 gemini-* 模型，或把风格参考换成 image（单张编辑底图）。"
            )
        return _openai_style(
            prompt, model=model, api_key=api_key, base_url=base_url,
            aspect_ratio=aspect_ratio, image_path=image_path,
            timeout_s=max(timeout_s, _OPENAI_MIN_TIMEOUT_S),
        )
    return _gemini_native(
        prompt, model=model, api_key=api_key, base_url=base_url,
        aspect_ratio=aspect_ratio, seed=seed, reference_paths=reference_paths,
        image_path=image_path, timeout_s=timeout_s,
    )


def _gemini_native(
    prompt: str,
    *,
    model: str,
    api_key: str,
    base_url: str,
    aspect_ratio: str,
    seed: "int | None",
    reference_paths: list,
    image_path: "str | None",
    timeout_s: float,
) -> bytes:
    """Gemini native：/v1beta/models/{model}:generateContent。"""
    url = f"{base_url.rstrip('/')}/v1beta/models/{model}:generateContent"

    parts: list = []
    for raw in ([image_path] if image_path else reference_paths):
        img = Path(raw)
        mime = "image/png" if str(img).lower().endswith(".png") else "image/jpeg"
        parts.append({"inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(img.read_bytes()).decode(),
        }})
    parts.append({"text": prompt})

    if image_path:
        # edit：输出尺寸跟随输入图，再传 aspectRatio 只会打架
        generation_config: dict = {"responseModalities": ["IMAGE", "TEXT"]}
    else:
        generation_config = {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio},
        }
    if seed is not None:
        generation_config["seed"] = seed

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"contents": [{"role": "user", "parts": parts}],
                  "generationConfig": generation_config},
            timeout=timeout_s,
        )
    except requests.exceptions.RequestException as e:
        raise _Retryable(f"请求失败：{e}") from e

    if not resp.ok:
        msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
        # 4xx（429 除外）是参数错误，重试多少次都一样
        if resp.status_code == 429 or resp.status_code >= 500:
            raise _Retryable(msg)
        raise RuntimeError(msg)

    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(f"响应不是合法 JSON：{e}") from e

    for cand in data.get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])

    raise RuntimeError("响应里没有图像数据（可能被安全策略拦了，或模型只回了文字）")


def _openai_style(
    prompt: str,
    *,
    model: str,
    api_key: str,
    base_url: str,
    aspect_ratio: str,
    image_path: "str | None",
    timeout_s: float,
) -> bytes:
    """OpenAI style：有底图走 /v1/images/edits，没有则 /v1/images/generations。"""
    root = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"}
    size = _ASPECT_TO_SIZE.get(aspect_ratio, "1024x1024")
    if aspect_ratio not in _OPENAI_EXACT_RATIOS:
        # 静默裁切最难查：出来的图「差不多对」，但构图紧了一圈
        print(
            f"  [warn] {model} 只原生支持 1:1 / 2:3 / 3:2，"
            f"aspect_ratio={aspect_ratio} 近似成 {size}，画面边缘会被裁掉。",
            file=sys.stderr,
        )

    try:
        if image_path:
            img = Path(image_path)
            if not img.exists():
                raise RuntimeError(f"编辑底图不存在：{img}")
            mime = "image/png" if str(img).lower().endswith(".png") else "image/jpeg"
            files = {
                "image": (img.name, img.read_bytes(), mime),
                "model": (None, model),
                "prompt": (None, prompt),
                "size": (None, size),
                "quality": (None, "high"),
            }
            resp = requests.post(
                f"{root}/v1/images/edits", headers=headers, files=files, timeout=timeout_s
            )
        else:
            resp = requests.post(
                f"{root}/v1/images/generations",
                headers={**headers, "Content-Type": "application/json"},
                json={"model": model, "prompt": prompt, "size": size, "quality": "high"},
                timeout=timeout_s,
            )
    except requests.exceptions.RequestException as e:
        raise _Retryable(f"请求失败：{e}") from e

    if not resp.ok:
        msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
        if resp.status_code == 429 or resp.status_code >= 500:
            raise _Retryable(msg)
        raise RuntimeError(msg)

    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(f"响应不是合法 JSON：{e}") from e

    items = data.get("data") or []
    if not items:
        raise RuntimeError(f"响应里没有图像数据；原始内容：{str(data)[:200]}")

    first = items[0]
    if first.get("b64_json"):
        return base64.b64decode(first["b64_json"])
    if first.get("url"):
        # laozhang 有时回 CDN 链接而不是内联 base64
        try:
            img_resp = requests.get(first["url"], timeout=60)
            img_resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise _Retryable(f"图片下载失败：{e}") from e
        return img_resp.content

    raise RuntimeError(f"响应里既没有 b64_json 也没有 url；字段：{list(first.keys())}")


def _is_openai_style(model: str) -> bool:
    return model.startswith("gpt-image")


def _key_env_for(model: str) -> str:
    return "LAOZHANG_OFFICIAL_API_KEY" if _is_openai_style(model) else "LAOZHANG_API_KEY"


def _resolve_api_key(model: str) -> str:
    """按模型选 key：gpt-image-* 在 official 分组，gemini-* 在默认分组。

    official key 没配就回退到普通 key —— 分组归属是 laozhang 后台的事，
    这边硬判「不可用」只会把能跑的情况也挡掉。
    """
    if _is_openai_style(model):
        return (
            _find_env_value("LAOZHANG_OFFICIAL_API_KEY")
            or _find_env_value("LAOZHANG_API_KEY")
        ).strip()
    return _find_env_value("LAOZHANG_API_KEY").strip()


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="laozhang 极简生图后端")
    ap.add_argument("batch", help="batch JSON 路径")
    ap.add_argument("--output-dir", required=True, help="图片输出目录")
    ap.add_argument("--dry-run", action="store_true", help="只打计划，不请求不写文件")
    ap.add_argument("--force", action="store_true", help="目标文件已存在时仍重新生成")
    args = ap.parse_args(argv)

    try:
        batch = json.loads(Path(args.batch).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[fatal] batch JSON 读不了：{e}", file=sys.stderr)
        return 1

    schema = batch.get("$schema_version")
    if schema != SUPPORTED_SCHEMA:
        print(
            f"[fatal] 不认识的 batch schema_version: {schema!r}"
            f"（本后端支持 {SUPPORTED_SCHEMA}）。上游 generate-assets 可能比本后端新，"
            "升级插件或换 backend: image-gen。",
            file=sys.stderr,
        )
        return 1

    # dry-run 不发请求，就不该要 key —— 新用户想先看看会出什么图，
    # 不该先被一堵凭证墙拦住。
    base_url = _find_env_value("LAOZHANG_BASE_URL") or DEFAULT_BASE_URL

    defaults = batch.get("defaults") or {}
    assets = batch.get("assets") or []
    out_dir = Path(args.output_dir)

    # 模型优先级：asset.model > defaults.model > LAOZHANG_MODEL > 内置默认。
    # 配置文件压过环境变量，与 .env 的查找同序 —— 一个系统里只该有一套答案。
    default_model = (
        defaults.get("model")
        or _find_env_value("LAOZHANG_MODEL")
        or DEFAULT_MODEL
    )

    # key 按模型家族分头检查：gpt-image-* 在 official 分组，用的是另一把。
    # 跑到第一张图才发现缺 key，等于白等一轮网络往返。
    if not args.dry_run:
        for m in sorted({a.get("model") or default_model for a in assets}):
            if not _resolve_api_key(m):
                print(
                    f"[fatal] 模型 {m} 需要 {_key_env_for(m)}，没找到。"
                    "到 https://api.laozhang.ai 注册取 key 后写进项目 .env 或环境变量；"
                    "或在 asset-config.yaml 里改用别的 backend。",
                    file=sys.stderr,
                )
                return 1

    refs = list(defaults.get("reference_paths") or [])
    if len(refs) > MAX_REFERENCES:
        print(
            f"[fatal] reference_paths {len(refs)} 张，超过上限 {MAX_REFERENCES}。",
            file=sys.stderr,
        )
        return 1

    success = failed = skipped = 0
    failed_assets: list = []

    for asset in assets:
        name = asset.get("name") or asset.get("filename") or "?"
        filename = asset.get("filename")
        prompt = asset.get("prompt") or ""
        if not filename:
            print(f"[error] asset {name!r} 缺 filename，跳过", file=sys.stderr)
            failed += 1
            failed_assets.append({"name": name, "error": "缺 filename"})
            continue

        target = out_dir / filename

        if args.dry_run:
            print(f"  [plan] {name} -> {target}  (model={asset.get('model') or default_model})")
            continue

        if target.exists() and not args.force:
            print(f"  [skip] {name}（已存在，--force 可覆盖）")
            skipped += 1
            continue

        try:
            asset_model = asset.get("model") or default_model
            data = _generate_one(
                prompt,
                model=asset_model,
                api_key=_resolve_api_key(asset_model),
                base_url=base_url,
                aspect_ratio=asset.get("aspect_ratio") or defaults.get("aspect_ratio") or "1:1",
                seed=asset.get("seed", defaults.get("seed")),
                reference_paths=refs,
                image_path=asset.get("image"),
                timeout_s=DEFAULT_TIMEOUT_S,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            print(f"  [ok] {name} -> {target}")
            success += 1
        except Exception as e:      # 单张失败不中断整批：一张 429 不该毁掉 50 张
            print(f"  [error] {name}: {e}", file=sys.stderr)
            failed += 1
            failed_assets.append({"name": name, "error": str(e)})

    summary = {
        "total": len(assets),
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "failed_assets": failed_assets,
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)

    if failed == 0:
        return 0
    if success == 0 and skipped == 0:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
