# Bound PPT · PPT Agent

基于 [linux.do 帖子《应该是目前最强的PPT Agent，附上完整思路分享》](https://linux.do/t/topic/1782304) 的产品化实践仓库。

## 目录结构

- `docs/linux-do-1782304-ppt-agent-extract.md` — 帖子内容提取（设计思路 + 提示词原文）
- `docs/ppt-agent-interaction-flow.md` — 产品交互流程设计（六阶段流程、状态机、mock 契约）
- `docs/images/` — 帖子关键工作流截图
- `prototype/ppt-agent-prototype.html` — 可点击交互原型（单文件，内置 mock LLM 流式返回）

## 运行原型

```bash
cd prototype && python3 -m http.server 8931
# 打开 http://127.0.0.1:8931/ppt-agent-prototype.html
```

或直接双击 `prototype/ppt-agent-prototype.html` 在浏览器中打开。

## 工作流（借鉴自帖子）

需求调研 → 资料搜集 → 便利贴大纲 → 策划稿（Bento 线框）→ 设计稿（风格应用）→ 预览与导出
