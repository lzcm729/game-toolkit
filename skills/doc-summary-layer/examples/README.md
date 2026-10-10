# 示例与实战数据

## 目录布局（一种可行的摆法）

```
<工程仓库>/
  docs/design/                      # 详稿（SSOT）：各册正文、参数页、内容表 CSV、_manifest.json
  docs/design/README.md             # 三条数据流写在这里
  scripts/push_summary.py           # 项目侧适配器（飞书）
<摘要目录>/                          # 只在平台，或仓库里一个排除在工具范围外的目录
  系统分册/战斗/战斗规则.md          # 与详稿同相对路径
  ...
```

## 清单最小示例

```json
{
  "docs": [
    {"file": "系统分册/战斗/战斗规则.md", "node_token": "<飞书页的 node_token>", "content_sha1": "<正文 sha1 的前 12 位>"},
    {"file": "数值记录.md", "node_token": "<飞书页的 node_token>", "content_sha1": "<正文 sha1 的前 12 位>"}
  ],
  "sheets": [
    {"sheet_name": "敌人表", "file": "系统分册/战斗/敌人表/第一版.csv", "revision": 12}
  ]
}
```

`docs[].node_token` 是对表工具稳定要求键里的文档身份，**不得更改**；`sheets[].revision` 保留平台原值，给「资产是否落后于表」的检查用。

## 跑一遍

```bash
python scripts/check_summaries.py --summaries ./summaries --manifest docs/design/_manifest.json --dead-words ./dead-words.txt
python scripts/build_summary_pages.py --summaries ./summaries --out ./build/pages --manifest docs/design/_manifest.json \
       --rev "$(git rev-parse --short HEAD)" --ssot-root docs/design --profile feishu
# 然后由项目侧适配器按 build/pages/index.json 逐页发布并回读
```

## 一个 UE 多人项目 2026-09-15 的数据

- 详稿 25 份（另有裁决账本一份，最后定为只在平台、仓库不存），摘要 25 份；规则条数 15～114 条／份，规则长度上限 60 字。
- 先做过一版「整页镜像发布」并验过 26 页往返，被否：镜像会毁内嵌表与评论，读者也会把副本当真值。改摘要当天完成。
- 摘要由六个子任务按同一份样板并行提炼，人工抽查改了三处（一处旧口径、两处补参数页指向）。
- 摘要提炼时顺手翻出九处详稿里的旧口径残留（早已裁掉的说法还留在正文里），当晚全部补执行——摘要是一次很好的详稿体检。
- 摘要只放平台，仓库不存；大改后由人重写、脚本重推。
