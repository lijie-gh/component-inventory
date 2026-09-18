# 贡献指南

感谢你对本项目感兴趣！这是一个面向硬件工程师的电子元器件库存管理小工具，欢迎提 Issue、报 Bug、提需求，也欢迎直接提 PR。

## 报告问题

提交 Issue 时请尽量包含：

- 操作系统版本（如 Windows 11 23H2）
- 程序版本（`v1.0.0` 或源码 commit hash）
- 复现步骤
- 期望行为 vs 实际行为
- 报错截图或错误信息（如有）

## 本地开发

```bash
# 克隆
git clone https://github.com/lijie-gh/component-inventory.git
cd component-inventory

# 零第三方依赖，直接用系统 Python 运行
python main.py
```

要求 Python 3.7+，且标准库自带 tkinter（官方安装包默认勾选）。

## 代码结构

```
main.py            程序入口
core/              业务逻辑：数据库、嘉立创抓取、汇率、定价、i18n
ui/                tkinter 界面：主窗口、元件编辑、出入库、导入对话框
tools/             打包/构建工具（不随程序运行）
tests/             测试
assets/            图标等静态资源
```

## 提交前自检

```bash
python tests/run_all.py
```

## 命名与提交

- 分支名：`fix/xxx`、`feat/xxx`
- Commit message 用中文短句，说清楚"做了什么"，例如：`修复入库后库存数量未刷新`
