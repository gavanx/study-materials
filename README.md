# 📚 学习资料库

孩子学习资料的统一仓库，按「年级 → 科目 → 专题」组织。每个专题提供一种或多种格式：

| 格式 | 文件名 | 用途 |
|------|--------|------|
| 打印版 | `print.pdf` / `print-vertical.pdf` | A4 竖版打印，题目+答案 |
| 平板版 | `tablet.pdf` | 带书签，微信/阅读器打开 |
| 交互版 | `interactive.html` | 自包含单文件，翻页+点击看答案 |
| 源文件 | `source.md` | 可重新生成各格式 |

在线目录（GitHub Pages）：https://gavanx.github.io/study-materials/

## 目录

```
grade-4/math/         四年级数学
├── triangle/         三角形专项（基础→竞赛）
└── operations-law/   运算定律与简便计算

grade-5/math/         五年级数学（含四升五衔接）
├── oral-math-a/      口算专项（提高篇）
├── thinking-1/       思维训练（一）
├── thinking-2/       思维训练（二·补充提高篇）
└── thinking-3/       思维训练（三·真正提高篇）

grade-5/general-math/ 通用计算
├── calc-basic/       计算专项（基础）
└── calc-improved/    计算专项（提高篇）
```

## 新增专题流程

1. 在对应 `grade-X/math/<topic>/` 下创建目录
2. 生成 `source.md`（用 exercise-gen 技能）
3. 生成 `print.pdf`（pandoc + weasyprint，见 exercise-gen-vertical/SKILL.md）
4. 如需平板使用，生成 `tablet.pdf`（带书签）；如需交互版，生成 `interactive.html`（单文件内联版）
5. 更新根目录 `index.html` 加一行
6. `git commit & push` → Pages 自动部署

## 命名规范

- 目录、文件名统一英文短名（`triangle`、`operations-law`），中文标题放在 index.html / README 中标注
- 配图放专题内 `figures/` 目录，md 内相对引用 `![](figures/fig-x.svg)`
