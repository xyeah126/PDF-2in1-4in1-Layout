# PDF 单页合并器 · PDF 2in1 / 4in1 / 6in1 / 8in1 Layout Tool

> 🖨️ 把多份**单页 PDF** 拼版在一张 A4 / A3 纸上，打印或共享一目了然。
> 矢量保真、文件超出容量自动分页、合并预览（滚轮缩放 / 手型拖动）、导出 PDF / JPG / PNG，Windows 一键打包成单文件 exe。

<p align="center">
  <a href="#运行截图">
    <img src="pdf_merger/app_preview.png" width="760" alt="软件运行截图">
  </a>
</p>

<p align="center">
  <a href="https://github.com/xyeah126/PDF-2in1-4in1-Layout/releases/tag/v0.8.3">
    <img alt="release v0.8.3"
         src="https://img.shields.io/badge/Release-v0.8.3-%232563EB?style=for-the-badge&logo=github&labelColor=%23111827">
  </a>
  &nbsp;
  <a href="#测试">
    <img alt="39 tests passed"
         src="https://img.shields.io/badge/Tests-39_passed-%2316A34A?style=for-the-badge&labelColor=%23111827">
  </a>
  &nbsp;
  <img alt="platform"
       src="https://img.shields.io/badge/Platform-Windows%2010%2F11%20%7C%20Python%203.10%2B-%230891B2?style=for-the-badge&logo=Windows&logoColor=white&labelColor=%23111827">
</p>

***

## 🎯 它解决什么问题

你手上有几十份「一页一份」的 PDF（试卷、作业、讲义、发票、处方、报告、快递面单……），
想要**一张纸打印多份**，却不想一页一页丢进 Word / Acrobat / 在线工具排版：

- ❌ Word 拖进去缩放错位、分辨率糊、排版来回调

- ❌ 在线 PDF 合并工具需要上传、泄露隐私、网速慢还带水印

- ❌ 打印驱动自带 N-up 会把 PDF 当图片光栅化、字发虚 / 发花

- ❌ 每次都要重新设置文件顺序、边距、页大小

**PDF 单页合并器** 一次性解决以上痛点：

1. 拖入或点选多份 PDF → 立即矢量合并渲染（**所见即所得**）
2. 选 2 / 4 / 6 / 8 合 1 模式、纸张方向、边距
3. 一键导出 PDF（矢量保真）/ JPG / PNG（300 DPI 可调）
4. 文件超出容量**自动分页**（例：3 个文件 + 2 合 1 → 输出 2 页）

***

## ✨ 核心特性

| 类别          | 能力                                                          |
| ----------- | ----------------------------------------------------------- |
| **合并模式**    | 2 合 1 / 4 合 1 / 6 合 1 / 8 合 1，支持 A4 / A3 × 横 / 纵            |
| **自动分页**    | 文件数超过模式容量自动翻页，每页用相同缩小格式排版                                   |
| **预览交互**    | 合并且所见即所得预览，**手型拖动 + 鼠标滚轮缩放**（0.25× \~ 6×），多页纵向拼接显示          |
| **矢量保真**    | 导出 PDF 使用 PyMuPDF `show_pdf_page`，纯矢量合并，文字/线条永远不糊           |
| **可调参数**    | 横向间距 / 纵向间距 / 外边距 三项 mm 级独立调整；JPG·PNG 导出 DPI 默认 300         |
| **持久化**     | 下次打开自动恢复**上次的文件列表 + 设置 + 选择项**，一键继续上次任务                     |
| **导出格式**    | PDF（单文件多页）/ JPG / PNG（多页自动生成 `xxx_p1.jpg`、`xxx_p2.jpg`）     |
| **界面字体**    | 全中文黑体加粗（SimHei bold），无英文默认字体导致的发虚                           |
| **界面布局**    | 三栏可拖拽分隔条：预览 57% / 中部三卡 27% / 日志+导出 16%                      |
| **单文件 exe** | Windows `build.bat` 一键 PyInstaller 打包，无黑命令行、带图标、带版本号        |
| **轻量依赖**    | 仅 `customtkinter / PyMuPDF / Pillow`，无 Electron / Qt 等重型运行时 |

***

## 🚀 三种使用方式

### 方式 1 · 直接下载源码包（最快）

1. 从 [Releases 页面](https://github.com/xyeah126/PDF-2in1-4in1-Layout/releases) 下载 **`pdf_merger_v0.8.3.zip`**（或仓库首页绿色 Code → Download ZIP）
2. 解压后进入目录，**双击** **`build.bat`**
3. 构建完成会在同目录生成 `PDFMerger_v0.8.3.exe`，双击即可使用

> 💡 `build.bat` 会自动：装 Python 依赖 → 用 PyInstaller 打包 → 把 exe 输出到同目录 → 完成后开一个文件浏览器窗口。
> 如果你已经装了 Python >= 3.10，整个过程 1 分钟内完成。

### 方式 2 · 源码直接运行（开发 / 调试）

```bash
# Windows PowerShell / CMD 都可以
git clone https://github.com/xyeah126/PDF-2in1-4in1-Layout.git
cd PDF-2in1-4in1-Layout
pip install -r requirements.txt
python pdf_merger/main.py
```

### 方式 3 · 作为模块调用（脚本批处理）

```python
from pdf_merger.config import MergeConfig, validate
from pdf_merger.pdf_engine import build_merged, export

cfg = validate(MergeConfig(mode=4, page_size="A4", orientation="横向",
                           gap_h_mm=10, gap_v_mm=10, margin_mm=10,
                           dpi=300, export_format="pdf"))

doc = build_merged([
    "report_01.pdf", "report_02.pdf",
    "report_03.pdf", "report_04.pdf",
])
try:
    paths = export(doc, "output/handout.pdf", cfg)
finally:
    doc.close()
print(paths)   # ["output/handout.pdf"]（超过一页时自动多页）
```

***

## 🖥️ 界面导览

```
┌────────────────────────────────────────────────────────────────────┐
│  PDF 单页合并器 v0.8.3                           [－] [1:1] [＋]  │ ← 缩放工具
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ 合并预览区（57% 高度）                                         │ │
│  │ · 多页纵向拼接 · 悬停即手型 · 滚轮缩放 · 拖动平移               │ │
│  │ · 4 合 1 · A4 横向 · 2×2 · 间距 10/10mm · 9 个文件 · 共 3 页│ │ ← 元信息栏
│  └──────────────────────────────────────────────────────────────┘ │
│  ┌────── 输入文件 ──────┐┌── 合并设置 ──┐┌── 页间距 ───────────┐ │ ← 中部三卡（27%）
│  │ 1. report_01.pdf    ▲││ 4 合 1  A4  ││ 横 [10] mm          │ │
│  │ 2. report_02.pdf    ▼││ 横○  纵●    ││ 纵 [10] mm          │ │
│  │ 3. report_03.pdf  删 ││ DPI [300]   ││ 外 [10] mm          │ │
│  │ ...                清││              ││                      │ │
│  │                    + ││              ││                      │ │
│  └──────────────────────┘└──────────────┘└──────────────────────┘ │
│  ┌── 运行日志 ───────────────────────────┐┌── 导出 ────────────┐ │ ← 底部（16%）
│  │ ✅ 打开文件 report_01.pdf              ││ 格式 ⭘ PDF ○ JPG  │ │
│  │ ✅ 打开文件 report_02.pdf              ││       ○ PNG       │ │
│  │ 🟢 共 9 个文件，按 4合1 排成 3 页      ││ 导出 → PDFMerger  │ │ ← 另存为(右对齐)
│  │ ✅ 导出完成：共 1 个文件 → D:\out\     ││     v0.8.3        │ │
│  └────────────────────────────────────────┘└────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

- **输入文件卡**（左右布局）：左侧蓝色高亮当前选中文件，右侧 5 个竖排按钮 — 上移 / 下移 / 删除 / 清空 / 添加

- **运行日志**：四级色标（✅ ok / 🔵 info / 🟡 warn / ❌ error），便于排查"某个 PDF 打不开"的问题

- **另存为按钮**：整体**右对齐**，符合 Windows 经典「底部操作区在右下」习惯

***

## 📦 项目结构

```
PDF-2in1-4in1-Layout/
├── LICENSE                       MIT
├── README.md                     本文件
├── RELEASE_NOTES_v0.8.3.md       本次 Release 详细更新说明
├── .gitignore                    排除 zip / pycache / 用户配置 json
├── requirements.txt              根目录直接 `pip install -r requirements.txt`
├── build.bat                     Windows 一键打包（exe 输出到同目录）
├── version_info.txt              exe 右键 → 属性 → 版本信息 v0.8.3
└── pdf_merger/
    ├── main.py                   入口（可选安装 tkinterdnd2 启用拖拽）
    ├── app.py                    UI 主程序 · customtkinter 三栏布局
    ├── pdf_engine.py             合并核心：PyMuPDF + Pillow（自动分页 / 预览拼图 / 多图导出）
    ├── worker.py                 后台导出线程（Bus 队列消息 → 主线程安全回 UI）
    ├── bus.py                    Bus：log / progress / done / error 四级回调，跨线程零锁
    ├── config.py                 MergeConfig dataclass + validate() 归一化
    ├── persistence.py            JSON 持久化：设置 + 文件列表 + 版本迁移（SETTINGS_VERSION）
    ├── build.spec                PyInstaller 配置（无控制台 / 单文件 / exe 名带版本号）
    ├── bump_version.py           一键升级版本号：同步 version.py 与 version_info.txt
    ├── version.py                主版本号（0.8.3）
    ├── requirements.txt          同根目录，保持子包独立可安装
    ├── make_icon.py / app.ico    应用图标（4 色几何蓝紫渐变）
    ├── smoke_ui.py               UI 冒烟测试（Xvfb 虚拟显示）
    ├── smoke_preview.py          预览管线冒烟
    ├── test_engine.py            39 项 pytest（版式 / 多页 / 导出 / 预览 / 持久化）
    └── app_preview.png           README 与 Release 展示用运行截图
```

***

## 🧪 测试

```bash
pip install pytest pillow pymupdf customtkinter
python -m pytest pdf_merger/test_engine.py -q      # 39 passed（版式 / 多页 / 导出 / 预览 / 持久化）
python pdf_merger/smoke_ui.py                      # UI_SMOKE_OK
python pdf_merger/smoke_preview.py                 # PREVIEW_PIPELINE_OK
```

**关键测试覆盖**：

- 3 个文件 + 2 合 1 → 输出 2 页（第 2 页只有第 1 个槽位有内容）

- 所有模式（2/4/6/8）× 多文件边界的页数公式：`页数 = ceil(n / cap)`

- PDF 多页导出、JPG/PNG 多页自动生成带 `_p1/_p2` 后缀、单页保持原名兼容

- 预览 PNG 结构校验（多页时 `height > 1.4 × width`，确认纵向拼接生效）

- JSON 持久化版本迁移（DPI 200 → 300 字段不丢）

***

## 🧩 技术选型（为什么用这些？）

| 需求     | 选择                                                                 | 原因                                                        |
| ------ | ------------------------------------------------------------------ | --------------------------------------------------------- |
| GUI 框架 | **customtkinter**                                                  | 原生 tkinter 美化版，打包后 30 MB；对比 PyQt/Electron 少 10× 体积，单机无运行时 |
| PDF 引擎 | **PyMuPDF（pymupdf）**                                               | `show_pdf_page` 直接**矢量嵌套**，输出 PDF 体积小、文字可搜索、永不降质          |
| 预览拼图   | **Pillow**                                                         | PyMuPDF 单页 `get_pixmap` 出 RGB，多页 PNG 合并 + LANCZOS 缩放，高清   |
| 后台任务   | **Bus 队列 + worker 线程**                                             | 避免 tkinter 跨线程操作控件崩溃；主线程 50 ms 轮询队列分发                     |
| 打包     | **PyInstaller +** **`console=False`** **+** **`version_info.txt`** | 单文件 exe，无黑命令行，右键属性版本信息完整                                  |
| 持久化    | **标准库 json**                                                       | 用户设置 + 文件列表 + 版本号迁移；无 SQLite / YAML 重型依赖                  |

***

## 🛠️ 常见问题

<details>
<summary><strong>Q1: 构建后 <code>PDFMerger_v0.8.3.exe</code> 在哪里？</strong></summary>

双击 `build.bat` 后，**exe 会出现在你解压 / 打开 build.bat 的那个根目录**，不是 pdf\_merger 子目录。脚本最后一行会 `explorer /select,...` 帮你定位到它。

</details>

<details>
<summary><strong>Q2: 为什么 3 个文件选 2 合 1 会输出 2 页？</strong></summary>

这是**刻意设计**的自动分页：2 合 1 每页容量 = 2，前 2 个文件排满第 1 页，第 3 个文件按相同缩小格式排在第 2 页的第 1 个槽位（第 2 个槽位留空），这样打印时每张纸都对得上原文件顺序，不会漏。页数公式：`ceil(文件数 / 模式容量)`。

</details>

<details>
<summary><strong>Q3: JPG / PNG 导出后文件名带了 <code>_p1</code> / <code>_p2</code>？</strong></summary>

为了区分多页结果：多页导出会自动加页码后缀（`output_p1.jpg`, `output_p2.jpg`…）。如果你的文件数恰好等于模式容量（如 4 个文件 + 4 合 1 = 1 页），导出会**保持原名兼容旧行为**，不加后缀。

</details>

<details>
<summary><strong>Q4: 预览清晰度不够？</strong></summary>

预览默认 1600 px 宽度高清渲染 + LANCZOS 缩放。屏幕显示发糊通常是 Windows 缩放 > 125% 导致 tkinter DPI 未感知，可在 `app.py` 中 `App.__init__` 前加上：

```python
import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(2)
```

</details>

<details>
<summary><strong>Q5: 关闭程序后下次打开能恢复文件列表和设置吗？</strong></summary>

可以。程序会在 `pdf_merger_config.json`（exe 同目录 / main.py 同级）保存：合并模式 / 纸张 / 方向 / 三项间距 / DPI / 导出格式 + 文件完整路径列表 + 当前选中项。清空文件时对应列表也会同步清空。

</details>

<details>
<summary><strong>Q6: 能不能支持 9 合 1 / 16 合 1 / 自定义网格？</strong></summary>

暂不支持。如果需要，修改 `config.py` 里的 `GRID` 映射表和 GUI `mode_seg` 选项即可扩展，其余布局逻辑（自动分页 / 预览 / 导出 / 测试参数化）不用改。

</details>

***

## 📋 更新日志 / 版本历史

详细 Release Notes 见：

- [RELEASE\_NOTES\_v0.8.3.md](./RELEASE_NOTES_v0.8.3.md)（v0.8.3 全量更新说明，含 v0.8.2 / v0.8.1 里程碑逐项列举）

- [Releases 页面](https://github.com/xyeah126/PDF-2in1-4in1-Layout/releases)（每次版本构建产物）

**当前版本 v0.8.3 关键更新**：

- 三栏布局比例最终调至 **57% / 27% / 16%**

- 修复 tkinter 3.14+ `sashpos → sash_place` API 不一致导致三栏一直均分

- v0.8.2 里程碑：**自动分页**、**多页预览拼接**、**全黑体加粗字体兜底**、**滚动条智能显隐**

***

## 📜 License

**MIT License** — 免费商用、修改、分发，保留 LICENSE 版权声明即可。

***

## 🙏 致谢

- [PyMuPDF](https://github.com/pymupdf/PyMuPDF)：最棒的 Python PDF 工具库

- [customtkinter](https://github.com/TomSchimansky/CustomTkinter)：现代 tkinter UI 美化

- 你 — 如果你觉得好用，点个 ⭐ Star 就是对作者最好的鼓励！

