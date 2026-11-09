"""假 CLI 只回放协议，测试不触发模型也不读取凭证。"""
import json
import os
from pathlib import Path
import sys
import subprocess
import time

args = sys.argv[1:]
log = {"args": args, "cwd": Path.cwd().as_posix(),
       "config_dir": os.environ.get("CLAUDE_CONFIG_DIR"),
       "cwd_entries": sorted(p.name for p in Path.cwd().iterdir())}
path = Path(os.environ["FAKE_CLAUDE_LOG"])
with path.open("a", encoding="utf-8", newline="\n") as stream:
    stream.write(json.dumps(log) + "\n")
if args[-1] == "timeout-tree":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    print(f"child_pid={child.pid}", flush=True)
    time.sleep(600)
if args[-1] == "invalid-once":
    previous = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if sum(call["args"][-1] == "invalid-once" for call in previous) == 1:
        print("synthetic non-JSON output")
        sys.exit(0)
print(json.dumps({"type": "system", "subtype": "init", "model": "fake-model", "claude_code_version": "0.fake"}))
if args[-1] == "partial":
    sys.exit(0)
if args[-1] == "error":
    print(json.dumps({"type": "result", "subtype": "error_max_budget_usd", "is_error": True}))
    sys.exit(1)
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "Synthetic answer", "total_cost_usd": 0}))
