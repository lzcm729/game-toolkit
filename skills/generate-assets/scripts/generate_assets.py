#!/usr/bin/env python3
"""
资源生成脚本 - 使用 Nano Banana Pro (Gemini 3 Pro Image) 生成游戏资源

用法:
    python scripts/generate_assets.py items           # 生成物品图标
    python scripts/generate_assets.py characters      # 生成人物头像
    python scripts/generate_assets.py all             # 生成所有资源
    python scripts/generate_assets.py items watch     # 只生成匹配的物品
    python scripts/generate_assets.py list            # 列出可生成的资源

按 Ctrl+C 可随时中断

物品图片配置:
    每个物品的 prompts 存储在 assets/items/{item_id}/prompts.json
    格式: {"default": "...", "restored": "...", "reforged": "..."}
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
from urllib import request, error

# ============================================================================
# 配置
# ============================================================================

SCRIPT_DIR = Path(__file__).parent
# 从 .claude/skills/generate-assets/scripts/ 向上跳 4 层到项目根目录
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
ITEMS_DIR = ASSETS_DIR / "items"
CHARACTERS_DIR = ASSETS_DIR / "characters"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
DATA_DIR = ASSETS_DIR / "data"
ITEMS_CSV = DATA_DIR / "Items_Base.csv"

# 从 .env 文件加载 API 密钥
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
# 统一风格定义
# ============================================================================

STYLE = {
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

# ============================================================================
# 物品数据读取
# ============================================================================

def load_items_from_csv() -> dict:
    """从 CSV 读取物品列表"""
    items = {}
    if not ITEMS_CSV.exists():
        print(f"Warning: Items CSV not found: {ITEMS_CSV}")
        return items

    with open(ITEMS_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_id = row.get("ID", "").strip()
            if item_id:
                items[item_id] = {
                    "category": row.get("Category", ""),
                    "names": {
                        "default": row.get("Name_Default", ""),
                        "restored": row.get("Name_Restored", ""),
                        "reforged": row.get("Name_Reforged", ""),
                        "counterfeit": row.get("Name_Counterfeit", ""),
                    }
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

# ============================================================================
# 人物定义 (保持硬编码，后续可迁移)
# ============================================================================

CHARACTERS = {
    "emma": {
        "name": "Emma",
        "description": "Young professional woman facing unemployment",
        "emotions": {
            "neutral": "a young professional woman in her late 20s, Asian features, neat business attire, slightly tired but composed, neutral expression",
            "grateful": "a young professional woman in her late 20s, Asian features, business attire, genuinely grateful, relieved smile with tearful eyes of joy",
            "resentful": "a young professional woman in her late 20s, Asian features, business attire, resentful bitter expression, disappointed eyes",
            "desperate": "a young professional woman in her late 20s, Asian features, disheveled appearance, desperate pleading, tear-stained anxious face",
            "angry": "a young professional woman in her late 20s, Asian features, business attire, angry confrontational, furrowed brows and tight lips",
        }
    },
    "zhao": {
        "name": "Old Zhao",
        "description": "Retired veteran with comrade's relics",
        "emotions": {
            "neutral": "an elderly Chinese military veteran in his 70s, weathered dignified face, worn neat clothes, stoic neutral, proud bearing",
            "grateful": "an elderly Chinese military veteran in his 70s, weathered face, grateful expression with respectful slight bow, misty appreciative eyes",
            "resentful": "an elderly Chinese military veteran in his 70s, weathered face, deeply hurt resentful look, betrayed disappointed dignity",
            "desperate": "an elderly Chinese military veteran in his 70s, weathered face, desperate pleading, trembling dignity with moist eyes",
            "angry": "an elderly Chinese military veteran in his 70s, weathered face, righteous angry expression, military bearing, intense eyes",
        }
    },
    "lin": {
        "name": "Mr. Lin",
        "description": "Fallen wealthy merchant, unaware of treasure",
        "emotions": {
            "neutral": "a middle-aged Chinese man in his 50s, once wealthy now fallen, expensive but worn suit, slightly dismissive, faded elegance",
            "grateful": "a middle-aged Chinese man in his 50s, worn elegant suit, surprised grateful expression, unexpected appreciation",
            "resentful": "a middle-aged Chinese man in his 50s, worn elegant suit, resentful bitter, wounded pride with cold disdainful eyes",
            "desperate": "a middle-aged Chinese man in his 50s, disheveled expensive clothes, desperate humiliated, fallen pride with pleading eyes",
            "angry": "a middle-aged Chinese man in his 50s, worn elegant suit, indignant angry, offended dignity and confrontational stance",
        }
    },
    "susan": {
        "name": "Susan",
        "description": "Fashionable socialite with fake goods",
        "emotions": {
            "neutral": "a glamorous Chinese woman in her 40s, heavy makeup, designer clothes, confident slightly haughty expression",
            "grateful": "a glamorous Chinese woman in her 40s, designer clothes, relieved grateful, facade softening with genuine smile",
            "resentful": "a glamorous Chinese woman in her 40s, designer clothes, offended resentful, wounded pride and dismissive posture",
            "desperate": "a glamorous Chinese woman in her 40s, makeup smeared, desperate panicked, facade crumbling with fearful eyes",
            "angry": "a glamorous Chinese woman in her 40s, designer clothes, furious angry, exposed defensive with threatening posture",
        }
    },
    "generic_male_young": {
        "name": "Young Male",
        "description": "Generic young male customer",
        "emotions": {
            "neutral": "a young Chinese man in his 20s, casual modern clothes, neutral everyday expression, ordinary appearance",
            "grateful": "a young Chinese man in his 20s, casual clothes, grateful happy with relieved smile",
            "resentful": "a young Chinese man in his 20s, casual clothes, disappointed resentful, sulking expression",
            "desperate": "a young Chinese man in his 20s, casual clothes, desperate anxious with worried eyes",
            "angry": "a young Chinese man in his 20s, casual clothes, angry upset, confrontational expression",
        }
    },
    "generic_male_middle": {
        "name": "Middle-aged Male",
        "description": "Generic middle-aged male customer",
        "emotions": {
            "neutral": "a middle-aged Chinese man in his 40s, plain work clothes, tired neutral expression, working class appearance",
            "grateful": "a middle-aged Chinese man in his 40s, work clothes, grateful relieved with sincere appreciation",
            "resentful": "a middle-aged Chinese man in his 40s, work clothes, bitter resentful, life-weary eyes",
            "desperate": "a middle-aged Chinese man in his 40s, work clothes, desperate pleading, family burden showing",
            "angry": "a middle-aged Chinese man in his 40s, work clothes, frustrated angry with restrained rage",
        }
    },
    "generic_male_old": {
        "name": "Elderly Male",
        "description": "Generic elderly male customer",
        "emotions": {
            "neutral": "an elderly Chinese man in his 60s-70s, simple traditional clothes, calm neutral expression, dignified aging",
            "grateful": "an elderly Chinese man in his 60s-70s, simple clothes, warmly grateful with wise appreciation",
            "resentful": "an elderly Chinese man in his 60s-70s, simple clothes, sad resentful, disappointed wisdom",
            "desperate": "an elderly Chinese man in his 60s-70s, simple clothes, desperate worried, life burden showing",
            "angry": "an elderly Chinese man in his 60s-70s, simple clothes, stern angry, righteous indignation",
        }
    },
    "generic_female_young": {
        "name": "Young Female",
        "description": "Generic young female customer",
        "emotions": {
            "neutral": "a young Chinese woman in her 20s, casual modern clothes, neutral everyday expression, ordinary appearance",
            "grateful": "a young Chinese woman in her 20s, casual clothes, grateful happy with bright smile",
            "resentful": "a young Chinese woman in her 20s, casual clothes, hurt resentful, disappointed expression",
            "desperate": "a young Chinese woman in her 20s, casual clothes, desperate tearful with anxious eyes",
            "angry": "a young Chinese woman in her 20s, casual clothes, upset angry, emotional expression",
        }
    },
    "generic_female_middle": {
        "name": "Middle-aged Female",
        "description": "Generic middle-aged female customer",
        "emotions": {
            "neutral": "a middle-aged Chinese woman in her 40s, modest practical clothes, neutral tired expression, hardworking appearance",
            "grateful": "a middle-aged Chinese woman in her 40s, practical clothes, grateful relieved with motherly warmth",
            "resentful": "a middle-aged Chinese woman in her 40s, practical clothes, bitter resentful, life-weary expression",
            "desperate": "a middle-aged Chinese woman in her 40s, practical clothes, desperate pleading, family burden showing",
            "angry": "a middle-aged Chinese woman in her 40s, practical clothes, protective angry with fierce determination",
        }
    },
    "generic_female_old": {
        "name": "Elderly Female",
        "description": "Generic elderly female customer",
        "emotions": {
            "neutral": "an elderly Chinese woman in her 60s-70s, simple traditional clothes, kind neutral expression, gentle aging",
            "grateful": "an elderly Chinese woman in her 60s-70s, simple clothes, warmly grateful with grandmotherly smile",
            "resentful": "an elderly Chinese woman in her 60s-70s, simple clothes, sad resentful, disappointed wisdom",
            "desperate": "an elderly Chinese woman in her 60s-70s, simple clothes, desperate worried, fragile dignity",
            "angry": "an elderly Chinese woman in her 60s-70s, simple clothes, stern disappointed, righteous anger",
        }
    },
}

# ============================================================================
# 背景定义
# ============================================================================

BACKGROUNDS = {
    "night_dashboard": {
        "name": "Night Dashboard",
        "description": "Pawn shop interior at night",
        "prompt": "Interior of a small traditional pawn shop at night, dimly lit by a warm desk lamp casting golden light on wooden counter, cluttered shelves with antique items in shadows, large window showing rainy city street with distant neon signs in blue and pink, raindrops on glass, moody atmospheric lighting, noir aesthetic, intimate and lonely atmosphere, no people, cinematic composition"
    },
    "day_counter": {
        "name": "Day Counter",
        "description": "Pawn shop counter during daytime",
        "prompt": "Interior of a traditional pawn shop during daytime, natural light coming through dusty windows, wooden counter with glass display case, old brass scale, antique items on shelves, vintage cash register, warm amber tones, lived-in atmosphere, realistic details, no people"
    },
    "morning_brief": {
        "name": "Morning Brief",
        "description": "Pawn shop at dawn",
        "prompt": "Early morning view inside a pawn shop, soft golden sunrise light streaming through window blinds, coffee cup steam rising, newspaper on counter, dust particles floating in light beams, quiet contemplative atmosphere, cinematic morning glow"
    },
}

# ============================================================================
# API 调用
# ============================================================================

def generate_image(prompt: str, asset_type: str, image_size: str = "1K") -> Optional[bytes]:
    """生成单张图片

    Args:
        prompt: 图片描述
        asset_type: 资源类型 (item/character/background)
        image_size: 图片尺寸 ("1K", "2K", "4K")
    """
    style = STYLE[asset_type]
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

            # 解析响应
            candidates = result.get("candidates", [])
            if not candidates:
                print(f" [!] No candidates", end="")
                continue

            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                # 检查所有可能的图片数据字段
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

    # 从 CSV 读取物品列表
    all_items = load_items_from_csv()
    if not all_items:
        print("No item data found")
        return

    # 过滤
    items = {k: v for k, v in all_items.items() if not filter_str or filter_str in k}
    if not items:
        print(f"No items matching '{filter_str}'")
        return

    generated = skipped = failed = no_prompts = 0

    for item_id, item_data in items.items():
        if interrupted:
            break

        # 加载 prompts
        prompts = load_item_prompts(item_id)
        if not prompts:
            print(f"[{item_id}] {item_data['category']} - no prompts.json, skipped")
            no_prompts += 1
            continue

        print(f"\n[{item_id}] {item_data['category']}")

        # 确保物品文件夹存在
        item_dir = ITEMS_DIR / item_id
        item_dir.mkdir(exist_ok=True)

        for state in ["default", "restored", "reforged", "counterfeit"]:
            if interrupted:
                break

            prompt = prompts.get(state)
            if not prompt:
                print(f"  ! {state}: no prompt, skipped")
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

            time.sleep(0.5)  # 避免速率限制

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

    chars = {k: v for k, v in CHARACTERS.items() if not filter_str or filter_str in k}
    if not chars:
        print(f"No characters matching '{filter_str}'")
        return

    generated = skipped = failed = 0

    for char_id, char_data in chars.items():
        if interrupted:
            break

        print(f"\n[{char_id}] {char_data['name']} - {char_data['description']}")

        char_dir = CHARACTERS_DIR / char_id
        char_dir.mkdir(exist_ok=True)

        for emotion, prompt in char_data["emotions"].items():
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

    bgs = {k: v for k, v in BACKGROUNDS.items() if not filter_str or filter_str in k}
    if not bgs:
        print(f"No backgrounds matching '{filter_str}'")
        return

    generated = skipped = failed = 0

    for bg_id, bg_data in bgs.items():
        if interrupted:
            break

        filepath = BACKGROUNDS_DIR / f"{bg_id}.png"

        if filepath.exists():
            print(f"+ {bg_id}: {bg_data['name']} (exists, skipped)")
            skipped += 1
            continue

        print(f"o {bg_id}: {bg_data['name']} ...", end="", flush=True)

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

    # 扫描物品 (按文件夹)
    if ITEMS_DIR.exists():
        for item_dir in ITEMS_DIR.iterdir():
            if item_dir.is_dir():
                files = list(item_dir.glob("*.png"))
                manifest["items"][item_dir.name] = {
                    "states": [f.stem for f in files],
                    "files": [f"{item_dir.name}/{f.name}" for f in files]
                }

    # 扫描人物
    if CHARACTERS_DIR.exists():
        for char_dir in CHARACTERS_DIR.iterdir():
            if char_dir.is_dir():
                files = list(char_dir.glob("*.png"))
                manifest["characters"][char_dir.name] = {
                    "emotions": [f.stem for f in files],
                    "files": [f"{char_dir.name}/{f.name}" for f in files]
                }

    # 扫描背景
    if BACKGROUNDS_DIR.exists():
        files = list(BACKGROUNDS_DIR.glob("*.png"))
        for f in files:
            manifest["backgrounds"][f.stem] = f.name

    manifest_path = ASSETS_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nManifest saved to: {manifest_path}")


def list_assets():
    """列出所有可生成的资源"""
    # 从 CSV 读取物品
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

    print("\nAvailable Characters:")
    for char_id, data in CHARACTERS.items():
        emotions = ", ".join(data["emotions"].keys())
        print(f"  + {char_id} ({data['name']}): {emotions}")

    print("\nAvailable Backgrounds:")
    for bg_id, data in BACKGROUNDS.items():
        print(f"  + {bg_id}: {data['name']}")

    # 统计
    total_items = items_with_prompts * 3
    total_chars = len(CHARACTERS) * 5
    total_bgs = len(BACKGROUNDS)
    print(f"\nSummary:")
    print(f"  Items: {items_with_prompts} with config ({total_items} images), {items_without_prompts} without config")
    print(f"  Characters: {len(CHARACTERS)} ({total_chars} images)")
    print(f"  Backgrounds: {total_bgs}")


def show_help():
    print(__doc__)


# ============================================================================
# 主程序
# ============================================================================

def main():
    print("=" * 50)
    print("  Pawn Shop Asset Generator (Python)")
    print("  Using Nano Banana Pro")
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
