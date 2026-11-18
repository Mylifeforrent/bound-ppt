# Bound PPT · PPT Agent

基于 [linux.do 帖子《应该是目前最强的PPT Agent，附上完整思路分享》](https://linux.do/t/topic/1782304) 的产品化实践仓库。当前设计版本：**v3**（顺序访谈、Agent 缺口建议、可撤销单页编辑、失效重跑与无障碍优化）。

## 目录结构

- `docs/linux-do-1782304-ppt-agent-extract.md` — 帖子内容提取（设计思路 + 提示词原文）
- `docs/ppt-content-sources.md` — 内容来源设计（v2.1：五类来源通道、接入优先级、数据契约、Agent 缺口建议）
- `docs/ppt-agent-interaction-flow.md` — 产品交互流程设计 v3（六阶段流程、状态机、失效传播、异常契约、无障碍基线）
- `docs/ppt-agent-ux-review.md` — 交互体验审查（v2 → v3 的问题清单、验证记录与剩余项）
- `docs/images/` — 帖子关键工作流截图
- `prototype/ppt-agent-prototype.html` — 可点击交互原型（单文件，内置 mock LLM 流式返回）

## 运行原型

```bash
cd prototype && python3 -m http.server 8931
# 打开 http://127.0.0.1:8931/ppt-agent-prototype.html
```

或直接双击 `prototype/ppt-agent-prototype.html` 在浏览器中打开。

## 工作流（v3）

素材接入（粘贴文本 / 拖拽文件 / URL，可选）→ 需求调研（素材消化 + Agent 缺口建议 + 顺序访谈 + 画像可回改）→ 便利贴大纲（拖拽 / 按钮 / 键盘，自动推进可暂停）→ 策划稿（Bento 线框，完成后才可确认）→ 设计稿（生成中可锁页、单页换版可撤销、微调、导出）

> 原则：一手素材优先，联网检索降级为补缺手段；素材槽为空时回退 v1 纯联网调研路径。
