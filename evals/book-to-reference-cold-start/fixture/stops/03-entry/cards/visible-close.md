<!-- capability_id: cap.ribbon.visible-close | revision: 1 | status: active | units: u03-01 -->

# 留下可回查的收尾记录

## R — 原文

> Keep the final ribbon visible until both harbor keepers sign the ledger.
>
> 译：在两位港口看守都签署记录簿之前，让最后一条纸带保持可见。
>
> — Nera Sample, The Ribbon Harbor Notebook, p.16

## I — 方法骨架

从可辨认输入得到有限的观察记录，不把记录当批准设计。

## A1 — 书中案例

书中的编造演练只说明本步骤，不证明其他项目的效果。

## A2 — 触发场景

- 推演要结束了，怎样保留没解决的观察？
- 纸带和记录对不上，还能签字收尾吗？

**与相邻卡的区分**

- 与 `gate-token` 区分：前者建立动作前的地点身份，本卡在收尾时核对最终纸带与记录并保留未决观察。

## E — 执行

### 分支 1（u03-01）

- 输入：已辨认地点与当前记录。
  1. 保留最后纸带可见，两人核对记录后签字；不符就停（p.16）。
- 输出：观察记录；条件不符先停止，不补造通过。

## B — 边界

原书未说明量化通过阈值。分支 1 不授权真实港口操作。
