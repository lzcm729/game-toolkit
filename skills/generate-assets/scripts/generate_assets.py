#!/usr/bin/env python3
"""
Game Asset Generator - 使用 Gemini API 生成游戏图片资源

数据驱动：资源定义从项目配置文件读取，不硬编码。

用法:
    python generate_assets.py items           # 生成物品图标
    python generate_assets.py characters      # 生成人物头像
    python generate_assets.py backgrounds     # 生成背景图
    python generate_assets.py all             # 生成所有资源
    python generate_assets.py items watch     # 只生成匹配的物品
    python generate_assets.py list            # 列出可生成的资源
    python generate_assets.py manifest        # 只生成资源清单

按 Ctrl+C 可随时中断

数据源:
    物品: CSV (assets/data/Items_Base.csv) + prompts.json (assets/items/{id}/prompts.json)
    人物: assets/characters/characters.json
    背景: assets/backgrounds/backgrounds.json
    风格: assets/style.json (可选覆盖)
"""

import csv
import os
import sys
import json
import base64
import time
import signal
from pathlib import Path
from typing import Optional

# Avoid broken pipe on Windows when piping output
try:
    from urllib import request, error
except ImportError:
    print("Error: urllib not available")
    sys.exit(1)

# ============================================================================
# 路径配置
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
# 从 skills/generate-assets/scripts/ 向上跳到 skill 根
SKILL_ROOT = SCRIPT_DIR.parent

# 查找项目根目录：向上查找直到找到包含 assets/ 或 package.json 的目录
def find_project_root() -> Path:
    # 先检查是否从 plugin 目录运行（.claude/skills/... 或 marketplaces/...）
    # 向上查找包含 assets/ 或 package.json 或 CLAUDE.md 的目录
    candidate = SCRIPT_DIR
    for _ in range(10):
        candidate = candidate.parent
        if (candidate / "package.json").exists() or (candidate / "CLAUDE.md").exists():
            return candidate
    # fallback: 当前工作目录
    return Path.cwd()

PROJECT_ROOT = find_project_root()
ASSETS_DIR = PROJECT_ROOT / "assets"
ITEMS_DIR = ASSETS_DIR / "items"
CHARACTERS_DIR = ASSETS_DIR / "characters"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
DATA_DIR = ASSETS_DIR / "data"

# ============================================================================
# .env 加载
# ============================================================================

def load_env():
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

load_env()

API_KEY = os.environ.get("NANO_BANANA_API_KEY") or os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("Error: NANO_BANANA_API_KEY or GEMINI_API_KEY not set")
    print("Please set the API key in .env file")
    sys.exit(1)

API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent"

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2

# 全局中断标志
interrupted = False

def signal_handler(sig, frame):
    global interrupted
    print("\n\n! Interrupt signal received, stopping...")
    interrupted = True

signal.signal(signal.SIGINT, signal_handler)

# ============================================================================
# 风格定义（默认值，可被 assets/style.json 覆盖）
# ============================================================================

DEFAULT_STYLE = {
    "item": {
        "prefix": "Watercolor illustration, single isolated object:",
        "suffix": "Hand-painted watercolor style, soft brush strokes, warm muted colors, fine ink outlines. Object floating on seamless cream white background, gentle watercolor splash behind object only, absolutely no background scene, no table, no surface, no environment, no context. Product illustration style, clean minimal, centered composition. No text, no labels, no brand names, no logos, no signatures. No frame, no border, no paper edges, no torn edges."
    },
    "character": {
        "prefix": "Hand-painted watercolor portrait of",
        "suffix": "Soft watercolor brush strokes, warm skin tones, gentle diffused lighting, visible paper texture, artistic organic edges, delicate ink outlines for features, expressive eyes. Bust portrait, cream-colored background with subtle color wash, emotional and intimate."
    },
    "background": {
        "prefix": "Atmospheric digital painting, game background art:",
        "suffix": "Cinematic composition, moody lighting, detailed environment, suitable for UI overlay, high quality game art, 16:9 aspect ratio feel but cropped to square."
    }
}

def load_style() -> dict:
    """加载风格配置，优先使用项目自定义"""
    style = dict(DEFAULT_STYLE)
    style_file = ASSETS_DIR / "style.json"
    if style_file.exists():
        try:
            with open(style_file, "r", encoding="utf-8") as f:
                custom = json.load(f)
            for key in custom:
                if key in style:
                    style[key].update(custom[key])
                else:
                    style[key] = custom[key]
            print(f"Loaded custom style from {style_file}")
        except (json.JSONDecodeError, Exception) as e:
            print(f"Warning: Failed to load style.json: {e}")
    return style

STYLE = load_style()

# ============================================================================
# 数据读取
# ============================================================================

def find_items_csv() -> Optional[Path]:
    """查找物品 CSV 文件"""
    # 默认路径
    default = DATA_DIR / "Items_Base.csv"
    if default.exists():
        return default
    # 搜索 data 目录下的 CSV
    if DATA_DIR.exists():
        for f in DATA_DIR.glob("*.csv"):
            return f
    return None

def load_items_from_csv() -> dict:
    """从 CSV 读取物品列表"""
    items = {}
    csv_path = find_items_csv()
    if not csv_path:
        print(f"Warning: No items CSV found in {DATA_DIR}")
        return items

    print(f"Loading items from: {csv_path.name}")
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_id = row.get("ID", "").strip()
            if not item_id:
                continue
            # 自动检测名称列（兼容不同项目的列名）
            names = {}
            for key, val in row.items():
                if key.startswith("Name_") or key.startswith("name_"):
                    state = key.split("_", 1)[1].lower()
                    names[state] = val
            items[item_id] = {
                "category": row.get("Category", row.get("category", "")),
                "names": names
            }
    return items

def load_item_prompts(item_id: str) -> Optional[dict]:
    """从物品文件夹加载 prompts.json"""
    prompts_file = ITEMS_DIR / item_id / "prompts.json"
    if not prompts_file.exists():
        return None
    try:
        with open(prompts_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Warning: {prompts_file} JSON error: {e}")
        return None

def load_characters() -> dict:
    """从 characters.json 读取人物定义"""
    config_file = CHARACTERS_DIR / "characters.json"
    if not config_file.exists():
        print(f"Warning: {config_file} not found")
        return {}
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Warning: Failed to load characters.json: {e}")
        return {}

def load_backgrounds() -> dict:
    """从 backgrounds.json 读取背景定义"""
    config_file = BACKGROUNDS_DIR / "backgrounds.json"
    if not config_file.exists():
        print(f"Warning: {config_file} not found")
        return {}
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Warning: Failed to load backgrounds.json: {e}")
        return {}

# ============================================================================
# API 调用
# ============================================================================

def generate_image(prompt: str, asset_type: str, image_size: str = "1K") -> Optional[bytes]:
    """生成单张图片"""
    style = STYLE.get(asset_type, STYLE.get("item"))
    full_prompt = f"{style['prefix']} {prompt}. {style['suffix']}"

    body = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {
            "imageConfig": {
                "aspectRatio": "1:1",
                "imageSize": image_size
            }
        }
    }

    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY
    }

    for attempt in range(1, MAX_RETRIES + 1):
        if interrupted:
            return None

        try:
            req = request.Request(API_ENDPOINT, data=data, headers=headers, method="POST")
            with request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            candidates = result.get("candidates", [])
            if not candidates:
                print(f" [!] No candidates", end="")
                continue

            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                img_data = (
                    part.get("inline_data", {}).get("data") or
                    part.get("inlineData", {}).get("data") or
                    part.get("file_data", {}).get("data")
                )
                if img_data:
                    return base64.b64decode(img_data)

            print(f" [!] No image data in response", end="")

        except error.HTTPError as e:
            print(f" [!] HTTP error {e.code}", end="")
        except error.URLError as e:
            print(f" [!] Network error: {e.reason}", end="")
        except Exception as e:
            print(f" [!] Error: {e}", end="")

        if attempt < MAX_RETRIES:
            print(f" (retry {attempt}/{MAX_RETRIES})", end="")
            time.sleep(RETRY_DELAY)

    return None

# ============================================================================
# 生成逻辑
# ============================================================================

def generate_items(filter_str: Optional[str] = None):
    """生成物品图标"""
    global interrupted

    print("\n" + "=" * 40)
    print("  Generate Item Icons")
    print("=" * 40 + "\n")

    ITEMS_DIR.mkdir(parents=True, exist_ok=True)

    all_items = load_items_from_csv()
    if not all_items:
        print("No item data found")
        return

    items = {k: v for k, v in all_items.items() if not filter_str or filter_str in k}
    if not items:
        print(f"No items matching '{filter_str}'")
        return

    generated = skipped = failed = no_prompts = 0

    for item_id, item_data in items.items():
        if interrupted:
            break

        prompts = load_item_prompts(item_id)
        if not prompts:
            print(f"[{item_id}] {item_data['category']} - no prompts.json, skipped")
            no_prompts += 1
            continue

        print(f"\n[{item_id}] {item_data['category']}")

        item_dir = ITEMS_DIR / item_id
        item_dir.mkdir(exist_ok=True)

        for state, prompt in prompts.items():
            if interrupted:
                break

            if not prompt:
                continue

            name = item_data["names"].get(state, state)
            filepath = item_dir / f"{state}.png"

            if filepath.exists():
                print(f"  + {state}: {name} (exists, skipped)")
                skipped += 1
                continue

            print(f"  o {state}: {name} ...", end="", flush=True)

            img_data = generate_image(prompt, "item")

            if img_data:
                filepath.write_bytes(img_data)
                print(" OK")
                generated += 1
            else:
                print(" FAIL")
                failed += 1

            time.sleep(0.5)

    print("\n" + "-" * 40)
    print(f"Items: {generated} generated, {skipped} existed, {failed} failed, {no_prompts} no config")
    if interrupted:
        print("(interrupted)")


def generate_characters(filter_str: Optional[str] = None):
    """生成人物头像"""
    global interrupted

    print("\n" + "=" * 40)
    print("  Generate Character Portraits")
    print("=" * 40 + "\n")

    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)

    all_chars = load_characters()
    if not all_chars:
        print("No character data found (need assets/characters/characters.json)")
        return

    chars = {k: v for k, v in all_chars.items() if not filter_str or filter_str in k}
    if not chars:
        print(f"No characters matching '{filter_str}'")
        return

    generated = skipped = failed = 0

    for char_id, char_data in chars.items():
        if interrupted:
            break

        print(f"\n[{char_id}] {char_data.get('name', char_id)} - {char_data.get('description', '')}")

        char_dir = CHARACTERS_DIR / char_id
        char_dir.mkdir(exist_ok=True)

        for emotion, prompt in char_data.get("emotions", {}).items():
            if interrupted:
                break

            filepath = char_dir / f"{emotion}.png"

            if filepath.exists():
                print(f"  + {emotion} (exists, skipped)")
                skipped += 1
                continue

            print(f"  o {emotion} ...", end="", flush=True)

            img_data = generate_image(prompt, "character")

            if img_data:
                filepath.write_bytes(img_data)
                print(" OK")
                generated += 1
            else:
                print(" FAIL")
                failed += 1

            time.sleep(0.5)

    print("\n" + "-" * 40)
    print(f"Characters: {generated} generated, {skipped} existed, {failed} failed")
    if interrupted:
        print("(interrupted)")


def generate_backgrounds(filter_str: Optional[str] = None):
    """生成背景图片"""
    global interrupted

    print("\n" + "=" * 40)
    print("  Generate Backgrounds")
    print("=" * 40 + "\n")

    BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)

    all_bgs = load_backgrounds()
    if not all_bgs:
        print("No background data found (need assets/backgrounds/backgrounds.json)")
        return

    bgs = {k: v for k, v in all_bgs.items() if not filter_str or filter_str in k}
    if not bgs:
        print(f"No backgrounds matching '{filter_str}'")
        return

    generated = skipped = failed = 0

    for bg_id, bg_data in bgs.items():
        if interrupted:
            break

        filepath = BACKGROUNDS_DIR / f"{bg_id}.png"

        if filepath.exists():
            print(f"+ {bg_id}: {bg_data.get('name', bg_id)} (exists, skipped)")
            skipped += 1
            continue

        print(f"o {bg_id}: {bg_data.get('name', bg_id)} ...", end="", flush=True)

        img_data = generate_image(bg_data["prompt"], "background", image_size="4K")

        if img_data:
            filepath.write_bytes(img_data)
            print(" OK")
            generated += 1
        else:
            print(" FAIL")
            failed += 1

        time.sleep(0.5)

    print("\n" + "-" * 40)
    print(f"Backgrounds: {generated} generated, {skipped} existed, {failed} failed")
    if interrupted:
        print("(interrupted)")


def generate_manifest():
    """生成资源清单"""
    manifest = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "items": {},
        "characters": {},
        "backgrounds": {}
    }

    if ITEMS_DIR.exists():
        for item_dir in ITEMS_DIR.iterdir():
            if item_dir.is_dir():
                files = list(item_dir.glob("*.png"))
                if files:
                    manifest["items"][item_dir.name] = {
                        "states": [f.stem for f in files],
                        "files": [f"{item_dir.name}/{f.name}" for f in files]
                    }

    if CHARACTERS_DIR.exists():
        for char_dir in CHARACTERS_DIR.iterdir():
            if char_dir.is_dir():
                files = list(char_dir.glob("*.png"))
                if files:
                    manifest["characters"][char_dir.name] = {
                        "emotions": [f.stem for f in files],
                        "files": [f"{char_dir.name}/{f.name}" for f in files]
                    }

    if BACKGROUNDS_DIR.exists():
        files = list(BACKGROUNDS_DIR.glob("*.png"))
        for f in files:
            manifest["backgrounds"][f.stem] = f.name

    manifest_path = ASSETS_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nManifest saved to: {manifest_path}")


def list_assets():
    """列出所有可生成的资源"""
    all_items = load_items_from_csv()

    print("\nAvailable Items (from CSV):")
    items_with_prompts = 0
    items_without_prompts = 0

    for item_id, data in all_items.items():
        prompts = load_item_prompts(item_id)
        if prompts:
            states = ", ".join(prompts.keys())
            print(f"  + {item_id} ({data['category']}): {states}")
            items_with_prompts += 1
        else:
            print(f"  - {item_id} ({data['category']}): [no prompts.json]")
            items_without_prompts += 1

    chars = load_characters()
    print("\nAvailable Characters:")
    for char_id, data in chars.items():
        emotions = ", ".join(data.get("emotions", {}).keys())
        print(f"  + {char_id} ({data.get('name', char_id)}): {emotions}")

    bgs = load_backgrounds()
    print("\nAvailable Backgrounds:")
    for bg_id, data in bgs.items():
        print(f"  + {bg_id}: {data.get('name', bg_id)}")

    # 统计
    total_items = sum(len(load_item_prompts(k) or {}) for k in all_items)
    total_chars = sum(len(d.get("emotions", {})) for d in chars.values())
    total_bgs = len(bgs)
    print(f"\nSummary:")
    print(f"  Items: {items_with_prompts} with config ({total_items} images), {items_without_prompts} without config")
    print(f"  Characters: {len(chars)} ({total_chars} images)")
    print(f"  Backgrounds: {total_bgs}")


def show_help():
    print(__doc__)


# ============================================================================
# 主程序
# ============================================================================

def main():
    print("=" * 50)
    print("  Game Asset Generator")
    print(f"  Project: {PROJECT_ROOT.name}")
    print("  Press Ctrl+C to interrupt")
    print("=" * 50)

    args = sys.argv[1:]
    command = args[0] if args else "help"
    filter_str = args[1] if len(args) > 1 else None

    if command == "items":
        generate_items(filter_str)
        if not interrupted:
            generate_manifest()
    elif command == "characters":
        generate_characters(filter_str)
        if not interrupted:
            generate_manifest()
    elif command == "backgrounds":
        generate_backgrounds(filter_str)
        if not interrupted:
            generate_manifest()
    elif command == "all":
        generate_items()
        if not interrupted:
            generate_characters()
        if not interrupted:
            generate_backgrounds()
        if not interrupted:
            generate_manifest()
    elif command == "manifest":
        generate_manifest()
    elif command == "list":
        list_assets()
    else:
        show_help()


if __name__ == "__main__":
    main()
