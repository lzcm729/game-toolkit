# 飞书适配：lark-cli 做法与踩过的坑（2026-09-15，CatFishing）

本文是适配器的**参考实现说明**，不是通用规范。换平台时只保留「适配器契约」（见 SKILL.md），这里的坑重新试一遍。
项目侧实现：CatFishing 工程仓库 `Scripts/push_feishu_summary.py`（读清单 → 加横幅 → 整页覆盖或保留内嵌表）。

## 做法

- 每份详稿在飞书知识库里有一页，清单 `_manifest.json` 记 `node_token`（页身份）与 `obj_token`；`lark-cli docs +update --doc <wiki 链接>` 直接认 wiki 链接。
- **不带内嵌表的页**：`--command overwrite --doc-format markdown --content @./页.md` 整页覆盖。标题不动。
- **带内嵌表（sheet）的页**：不能整页覆盖——markdown 里的 `<sheet>` 标签会**复制出一张新表、旧表消失**，策划在原表里填的值就丢了。做法：`+fetch --doc-format xml --detail with-ids` 取块列表 → 按「同一父级的连续非表格块」逐段 `block_delete` → 只剩表格 → `block_insert_after --block-id <标题块>` 把摘要插到最前面。
- 覆盖会丢掉页上的评论；流程里要写明。
- 发完回读（xml with-ids 数块、markdown 看关键句），别信 `ok:true`。

## 标记的坑（都在 markdown 模式踩到）

| 写法 | 结果 | 处理 |
|---|---|---|
| `**加粗**` 贴着全角标点（`**规则**。`） | 加粗失效或串位 | 正文里的 `**x**` 改成 `<b>x</b>`（构建脚本 `--profile feishu`） |
| 表格单元格里的 `**x**` 或 `<b>x</b>` | 变字面字符 | 单元格里去掉加粗标记 |
| 一段加粗跨了两行（源文件软换行） | 变字面 `\*\*` | 把段落写成一行再发；构建脚本按行处理，跨行的它不认 |
| 有序列表 `7.`～`13.` 被一段普通段落隔开 | 后半段从 1 重排；`append` 追加的「14.」也接着排 | 写成转义点的段落 `7\. ` `8\. `…，不用有序列表 |
| front matter（`--- … ---`） | 被当正文发上去（CRLF 检出时正则还会失手） | 发前先归一 CRLF→LF 再剥 front matter 与 `<title>` |
| `@./文件` 内容引用 | 只认 cwd 相对路径 | 临时文件写到 cwd 下再引用 |
| `<日期-主题>`、`w<1 kg` 这类尖括号 | 原样保留 | 不用处理，但回读确认一次 |

## 块操作的坑

- 列表外壳（ul/ol）没有块 id，真正的块是 li，且 li 与页级块不是同一个父级：`--start-block-id/--end-block-id` 的范围只能是同父级的连续块，删列表要按父级分段删。
- `block_delete` 之后**其它块的 id 不变**（09-15 实测：删完一段再按旧 id 删、替换、插入都成功）；`block_replace` 会给被替换的那块发**新 id**。
- markdown 模式的 `str_replace` 命中标题／列表项／引用块时只保留第一块，且照样报 success——改段落用 `block_replace` 打单块。
- 两次 fetch 之间属主可能自己动过页，diff 里的减项别默认是工具事故，先问。
- `lark-cli` 的 `+fetch` 等命令加 `--as user` 用公司账号身份；批量脚本把 `--as user --format json` 固定在 run 封装里。

## 一次发布的时间感

26 页整页覆盖加回读验证约十分钟；带内嵌表的页按段删块要多几次调用。摘要由六个子任务并行提炼、样板一份、人工抽查后再发，抽查真的抓到了错（道具册抄网那条写成了上一版口径）。
