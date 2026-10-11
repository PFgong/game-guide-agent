---
name: game-guide-research
description: "Live-web retrieval, verification and answer-writing playbook for game walkthroughs across online, single-player, mobile and mini-games. Use when you need to find where guides live for a given game type, construct effective multilingual search queries, judge whether a guide is still valid for the current version, or pick the right answer template for a question type."
---

# 游戏攻略检索与核验手册

给攻略团成员用的操作手册。**所有游戏事实必须来自实时检索，不得依赖模型记忆。**

## 何时加载

- 需要确认某款游戏该去哪些站点查攻略
- 检索多次未命中，需要换关键词/换语种/换源
- 需要判断一条攻略是否已被版本更新作废
- 需要按问题类型选择答案模板

## References

| 文件 | 用途 | 谁用 |
|------|------|------|
| `references/01-source-map.md` | 按游戏形态/地区检索的站点地图与优先级 | parser、crawler |
| `references/02-search-playbook.md` | 关键词构造、三语检索、失败降级路径 | crawler |
| `references/03-credibility-rules.md` | 可信度分级、时效判定、伪攻略识别 | verifier、crawler |
| `references/04-answer-templates.md` | 八类问题的答案模板 | writer |

## 三条铁律

1. **不编造**。查不到就写"缺口"，模型记忆里的游戏数值默认视为过期。
2. **标时效**。每条来源必须带发布/更新时间，答案必须标适用版本/区服。
3. **给直链**。图片必须是能直接渲染的绝对 URL，且核验过内容与问题相关。

## 标准检索动作序列

1. 中文关键词批次（国产游戏命中率最高）
2. 英文/日文关键词批次（交叉验证 + 补充细节，日系游戏必查日文源）
3. 站点内定向检索：进入 01-source-map.md 中对应游戏形态的优先站点，用站内搜索
4. 补缺：视频平台（B 站 / YouTube）抓实测流程；社区（NGA / 贴吧 / Reddit）抓边界情况与 BUG
5. 仍不足 → 换语种、换叫法（玩家黑话 ↔ 官方译名）、换问题切角（"怎么触发" ↔ "触发条件" ↔ "前置任务"）
