# -*- coding: utf-8 -*-
"""英文界面词典。

key 是**中文原文**（含 `{0}` 这类位置占位符），value 是英文译文。
改词条直接改这里即可；用户也可以用 `data/lang_en.json` 覆盖个别条目。

约定
----
- 漏翻的条目不会报错，只会原样显示中文，所以可以随时增量补充。
- 跑 `python tools/extract_ui_strings.py check` 能列出所有还没翻的界面文案。
- **不要**把这里当成数据翻译（Excel 表头别名、元件分类等不在此列）。
"""

TABLE = {
    # ---------------------------------------------------------- 界面骨架
    "⚙ 设置": "⚙ Settings",
    "设置": "Settings",
    "文件": "File",
    "工具": "Tools",
    "帮助": "Help",
    "筛选": "Filter",
    "关闭": "Close",
    "取消": "Cancel",
    "确定": "OK",
    "知道了": "Got it",
    "保存": "Save",
    "删除": "Delete",
    "编辑": "Edit",
    "浏览…": "Browse…",
    "退出": "Exit",
    "全部": "All",
    "无": "None",
    "个": "pcs",
    "提示": "Notice",
    "就绪": "Ready",
    "查询中…": "Querying…",
    "导入中…": "Importing…",
    "所有文件": "All files",
    "表格": "Table",
    "类型": "Type",
    "状态": "Status",
    "时间": "Time",
    "数量": "Quantity",
    "单位": "Unit",
    "分类": "Category",
    "封装": "Package",
    "厂商": "Manufacturer",
    "型号": "Model",
    "名称": "Name",
    "备注": "Remark",
    "来源": "Source",
    "库位": "Location",
    "库存": "Stock",

    # ---------------------------------------------------------- 元件与字段
    "C号": "C-No.",
    "C号 / 型号": "C-No. / Model",
    "（无C号）": "(no C-No.)",
    "型号 / MPN": "Model / MPN",
    "名称 / 描述": "Name / description",
    "名称/描述 *": "Name / description *",
    "厂商 / 品牌": "Manufacturer / brand",
    "参数值": "Value",
    "详细描述": "Description",
    "数据手册链接": "Datasheet URL",
    "来源 / 说明": "Source / note",
    "采购渠道": "Supplier",
    "库位明细": "Location detail",
    "元件库存_": "Inventory_",
    "元件库存_筛选结果_": "Inventory_filtered_",
    "实际数量": "Actual qty",
    "库存金额": "Stock value",
    "库存估值(¥)": "Stock value (¥)",
    "库存总数量": "Total quantity",
    "参考单价": "Ref. price",
    "参考单价(元)": "Ref. price (CNY)",
    "参考单价(按量)": "Ref. price (by qty)",
    "预警阈值": "Threshold",
    "元件种类": "Part types",
    "元件来源：": "Part source:",
    "出入库流水记录": "Stock transaction log",
    "最近 500 条出入库记录": "Latest 500 transactions",
    "查看该元件的出入库记录": "View this part's transactions",
    "元件 {0} 的出入库记录（最近 500 条）":
        "Transactions for {0} (latest 500)",
    "还没有出入库记录": "No transactions yet",

    # ---------------------------------------------------------- 来源
    "其它渠道": "Other",
    "嘉立创件": "LCSC parts",
    "其它渠道件": "Other parts",
    "仅嘉立创": "LCSC only",
    "仅其它渠道": "Other only",
    "仅显示嘉立创元件": "Show LCSC parts only",
    "仅显示其它渠道元件": "Show other-channel parts only",
    "嘉立创商城": "LCSC",
    "嘉立创 C 号": "LCSC C-No.",
    "嘉立创 C 号：": "LCSC C-No.:",
    "例：C1525": "e.g. C1525",
    "嘉立创元件必须填写 C 号": "LCSC parts require a C-number",
    "嘉立创商城元件（输入 C 号自动获取资料）":
        "LCSC part (enter C-number to fetch data)",
    "其它渠道元件（非嘉立创采购，手工录入）":
        "Other-channel part (not from LCSC, manual entry)",
    "该元件没有嘉立创 C 号": "This part has no LCSC C-number",
    "请选择带嘉立创 C 号的元件": "Please select parts that have an LCSC C-number",
    "库中没有嘉立创元件": "No LCSC parts in library",
    "嘉立创商城报价是美元，按此汇率折算成参考单价（元）":
        "LCSC quotes in USD; this rate converts it to CNY",
    "从嘉立创商城刷新资料": "Refresh data from LCSC",
    "刷新商城资料": "Refresh LCSC data",
    "刷新选中元件的商城资料": "Refresh LCSC data for selected",
    "刷新全部嘉立创元件资料（批量联网）": "Refresh all LCSC parts (batch, online)",
    "查询商城资料": "Fetch LCSC data",
    "尚未获取商城资料": "No LCSC data yet",
    "已从嘉立创商城获取元件资料": "Part data fetched from LCSC",
    "商城英文原文：": "Original English text:",
    "正在连接嘉立创商城…": "Connecting to LCSC…",
    "打开嘉立创商品页": "Open LCSC product page",
    "打开数据手册": "Open datasheet",
    "该元件没有数据手册链接": "This part has no datasheet link",
    "📄 有数据手册": "📄 Datasheet",

    # ---------------------------------------------------------- 录入
    "添加元件": "Add part",
    "＋ 添加元件": "＋ Add part",
    "编辑元件": "Edit part",
    "已保存修改": "Changes saved",
    "已新建元件": "Part created",
    "元件已存在，库存已追加": "Part exists; stock appended",
    "填完 C 号自动联网取资料，不用再点按钮":
        "Fetch LCSC data automatically after typing the C-number",
    "填入 C 号后点「查询商城资料」，自动带回型号、厂商、":
        "Enter a C-number and click \"Fetch LCSC data\" to retrieve model, manufacturer,",
    "填入 C 号后会自动联网查询（可在「设置」菜单里关闭），":
        "Auto-queries online after you type a C-number (can be turned off in Settings),",
    "自动带回型号、厂商、封装、价格与数据手册。":
        "It retrieves model, manufacturer, package, price and datasheet automatically.",
    "封装、价格与数据手册。": "package, price and datasheet.",
    "（建议先点「查询商城资料」自动补全信息）":
        "(click \"Fetch LCSC data\" first to fill in details)",
    "已识别 C 号，正在自动查询商城资料…":
        "C-number detected, fetching LCSC data…",

    # ---------------------------------------------------------- 出入库
    "入库": "Stock in",
    "出库": "Stock out",
    "盘点": "Stocktake",
    "库位调拨": "Transfer",
    "入库（增加库存）": "Stock in (increase)",
    "出库（消耗库存）": "Stock out (consume)",
    "盘点（把库存改为实际数量）": "Stocktake (set stock to actual count)",
    "库位调拨（在两个库位之间转移）": "Transfer (move between locations)",
    "入库数量": "Inbound qty",
    "出库数量": "Outbound qty",
    "调拨数量": "Transfer qty",
    "入库数量：": "Inbound quantity:",
    "源库位": "From location",
    "目标库位": "To location",
    "盘点调整": "Stocktake adjustment",
    "库存操作": "Stock actions",
    "操作人": "Operator",
    "默认操作人": "Default operator",
    "出入库流水里记录的经手人，可留空":
        "Operator recorded in transactions; may be left blank",
    "允许负库存（先出库、后补登记入库）":
        "Allow negative stock (ship first, register receipt later)",
    "默认关闭（库存不足就拒绝）；开启后可以先出库、后补登记":
        "Off by default (reject when short); when on you can issue first and register later",
    "出库允许负库存": "Allow negative stock on issue",
    "　　勾选后数量可以出成负数，并在备注里记下欠账，":
        "  When enabled the quantity may go negative and the shortfall is noted in the remark,",
    "提示：库位库存不足时会拒绝出库，避免出现负库存。":
        "Note: issuing more than the location holds is rejected, so stock can't go negative.",
    "提示：盘点会把该库位数量直接改为填写值，并记录差额流水。":
        "Note: stocktake sets the location quantity to the value you enter and logs the difference.",
    "库存与流水始终一致。": "Stock and transactions always stay consistent.",
    "此操作一次只能选一个元件": "This action works on one part at a time",
    "现有库存　{0}": "Current stock　{0}",

    # ---------------------------------------------------------- 统计与预警
    "有库存": "In stock",
    "无库存": "No stock",
    "零库存": "Zero stock",
    "缺货": "Out of stock",
    "充足": "OK",
    "偏低": "Low",
    "当前无库存": "No stock",
    "低库存预警": "Low stock",
    "显示低库存预警": "Show low-stock warning",
    "低库存预警阈值": "Low-stock threshold",
    "库存预警阈值": "Low-stock threshold",
    "库存数量 ≤ 该值时标红提醒（元件单独设置的阈值优先）":
        "Rows are flagged when stock ≤ this value (per-part threshold wins)",
    "显示全部": "Show all",
    "显示零库存元件": "Show zero-stock parts",
    "全部分类": "All categories",
    "清除筛选": "Clear filters",
    "清除所有筛选条件": "Clear all filters",

    # ---------------------------------------------------------- 批量导入
    "批量导入": "Batch import",
    "批量导入元件": "Batch import parts",
    "批量导入（Excel / CSV / 粘贴 BOM）": "Batch import (Excel / CSV / paste BOM)",
    "批量导入（追加库存）": "Batch import (append stock)",
    "批量导入（追加库存，未改资料）": "Batch import (stock appended, data kept)",
    "  从 Excel / CSV 文件导入  ": "  Import from Excel / CSV file  ",
    "  粘贴 C 号 / BOM 清单  ": "  Paste C-numbers / BOM list  ",
    " 预览（解析结果） ": " Preview (parsed result) ",
    "开始导入": "Start import",
    "选择文件：": "Choose file:",
    "（未选择文件）": "(no file selected)",
    "选择 Excel / CSV 文件": "Choose Excel / CSV file",
    "请先选择一个 Excel / CSV 文件。": "Please choose an Excel / CSV file first.",
    "  存放库位：": "  Storage location:",
    "导入到库位：": "Import into location:",
    "工作表：": "Sheet:",
    "未写数量时默认：": "Default when no quantity given:",
    "已存在的元件只追加库存、不覆盖已录入的资料":
        "Existing parts only get stock appended; entered data is kept",
    "支持 Excel（.xls / .xlsx）、CSV、以及网页导出的表格文件。\n":
        "Supports Excel (.xls / .xlsx), CSV and web-exported tables.\n",
    "支持 .xls（Excel 97-2003）、.xlsx、.csv，以及网页导出的表格文件；":
        "Supports .xls (Excel 97-2003), .xlsx, .csv and tables exported from web pages;",
    "每行一个元件，支持 C1525、C1525 100、C1525 x100、":
        "One part per line; accepts C1525, C1525 100, C1525 x100,",
    "以及立创 BOM 导出的整行文本：": "or full lines exported from LCSC BOM:",
    "表头不在第一行、前面有标题行都没关系。":
        "A header that isn't on the first row (with title rows above) is fine.",
    "表头会自动识别，常见列名（嘉立创C号 / 商品编号 / 编码 / 型号 / ":
        "Headers are detected automatically; common names (LCSC C-No. / part number / code / model /",
    "名称 / 数量 / 购买数量 / 单价 / 采购渠道…）都能直接对上号。":
        "name / qty / purchase qty / unit price / supplier … are recognized automatically.",
    "没有识别到表头，已按内容推测：": "No header row detected; guessed from content:",
    "核对上面的「识别列」和下方预览无误后，再点「开始导入」。\n":
        "Check the detected columns above and the preview below, then click \"Start import\".\n",
    "（可在下方预览里核对）": "(verify in the preview below)",
    "网页导出的表格": "Web-exported table",
    "Excel / CSV 表格": "Excel / CSV table",
    "Excel XML 表格": "Excel XML table",
    "Excel 工作簿": "Excel workbook",
    "Excel 工作簿（.xlsx）": "Excel workbook (.xlsx)",
    "Excel 97-2003（.xls）": "Excel 97-2003 (.xls)",
    "CSV / 文本": "CSV / text",
    "CSV 文件": "CSV file",
    "读取失败": "Read failed",
    "导入失败": "Import failed",
    "导入完成（有失败项）": "Import finished (with failures)",
    "没有可导入的内容": "Nothing to import",
    "没有找到可用的 C 号 / 型号列，请检查表格内容。":
        "No usable C-number / model column found. Please check the table.",
    "没有解析到任何 C 号，请检查输入格式。":
        "No C-number parsed. Please check the input format.",
    "这个工作表里没有可导入的记录，请换一个工作表试试":
        "No importable records in this sheet; try another one",
    "如果是 Excel 文件，可以先在 Excel 里另存为 .xlsx 或 .csv 再试。":
        "If it's an Excel file, try saving it as .xlsx or .csv in Excel first.",
    "解析出 {0} 条记录，合计 {1} 个": "Parsed {0} records, {1} pcs total",
    "解析出 {0} 个 C 号，合计 {1} 个": "Parsed {0} C-numbers, {1} pcs total",
    "识别列：{0}": "Detected columns: {0}",
    "已识别：{0}": "Detected: {0}",
    "表头在第 {0} 行，": "Header on row {0},",
    "（该文件有 {0} 个工作表，已选「{1}」）":
        "(the file has {0} sheets; \"{1}\" selected)",
    "无法读取这个文件：\n{0}\n\n{1}\n\n":
        "Cannot read this file:\n{0}\n\n{1}\n\n",
    "完成：成功 {0} 条（其中更新已有 {1} 条），":
        "Done: {0} succeeded ({1} updated existing),",
    "导入完成，共处理 {0} 条": "Import finished, {0} processed",
    "正在处理 {0}/{1}…": "Processing {0}/{1}…",
    "已处理 {0} 项": "{0} processed",
    "失败 {0} 条": "{0} failed",
    "成功 {0} 条，失败 {1} 条：\n\n{2}{3}": "{0} succeeded, {1} failed:\n\n{2}{3}",
    "\n… 另有 {0} 条": "\n… {0} more",
    " … 等 {0} 项": " … and {0} more",

    # ---------------------------------------------------------- 导出与备份
    "导出 CSV": "Export CSV",
    "导出为 CSV": "Export as CSV",
    "导出全部清单为 CSV": "Export full list as CSV",
    "导出当前筛选结果": "Export filtered results",
    "导出出入库流水": "Export transaction log",
    "导出流水 CSV": "Export log CSV",
    "导出完成": "Export complete",
    "导出失败": "Export failed",
    "没有可导出的数据": "No data to export",
    "没有可导出的记录": "No records to export",
    "备份数据库": "Back up database",
    "备份完成": "Backup complete",
    "备份失败": "Backup failed",
    "已导出到：\n{0}": "Exported to:\n{0}",
    "已导出 {0} 条到：\n{1}\n\n是否打开所在文件夹？":
        "Exported {0} rows to:\n{1}\n\nOpen the folder?",
    "已导出 {0} 条流水到：\n{1}\n\n是否打开所在文件夹？":
        "Exported {0} transactions to:\n{1}\n\nOpen the folder?",
    "数据库已备份到：\n{0}": "Database backed up to:\n{0}",
    "请手动打开：{0}": "Please open it manually: {0}",

    # ---------------------------------------------------------- 设置
    "常规设置…": "General settings…",
    "恢复默认设置": "Restore defaults",
    "恢复默认设置…": "Restore defaults…",
    "设置已恢复默认值": "Settings restored to defaults",
    "将把阈值、操作人、汇率、勾选项全部恢复成出厂默认值。\n":
        "This resets threshold, operator, exchange rate and all toggles to defaults.\n",
    "元件资料与库存数据不受影响。是否继续？":
        "Part data and stock records are not affected. Continue?",
    "添加元件时自动查询商城资料": "Auto-fetch LCSC data when adding a part",
    "新建元件时联网补全嘉立创商城资料": "Fetch LCSC data online for new parts",
    "删除元件前二次确认": "Confirm before deleting a part",
    "关掉后按 Delete 直接删除，不可恢复":
        "When off, Delete removes immediately and permanently",
    "美元汇率": "USD exchange rate",
    "美元汇率必须是大于 0 的数字":
        "Exchange rate must be a number greater than 0",
    "阈值必须是数字": "Threshold must be a number",
    "数量必须是数字": "Quantity must be a number",
    "入库数量必须是数字": "Inbound quantity must be a number",
    "默认数量必须是数字": "Default quantity must be a number",
    "数量必须大于 0": "Quantity must be greater than 0",
    "数量不能为负数": "Quantity cannot be negative",
    "打开数据目录": "Open data folder",
    "清空商城数据缓存": "Clear LCSC cache",
    "清空缓存": "Clear cache",
    "商城数据缓存已清空": "LCSC cache cleared",
    "商城数据缓存是空的": "LCSC cache is empty",
    "本地缓存": "Local cache",
    "已清理 {0} 条过期的商城缓存": "Cleared {0} expired LCSC cache entries",
    "当前缓存 {0} 条（约 {1:.0f} KB）。\n": "Cache holds {0} entries (~{1:.0f} KB).\n",
    "清空后下次查询会重新联网获取嘉立创数据。是否继续？":
        "Clearing means the next query will fetch from LCSC again. Continue?",
    "使用说明 / 关于": "Help / About",
    "刷新列表": "Refresh list",
    "批量刷新": "Batch refresh",
    "刷新失败": "Refresh failed",
    "部分刷新失败": "Partly failed",
    "部分元件刷新失败": "Some parts failed to refresh",
    "部分操作未完成": "Some operations did not complete",
    "正在刷新 0/{0} …": "Refreshing 0/{0} …",
    "正在刷新 {0}/{1} …{2}": "Refreshing {0}/{1} …{2}",
    "刷新完成：成功 {0} 个，失败 {1} 个": "Refresh done: {0} succeeded, {1} failed",
    "成功 {0} 个，失败 {1} 个：\n\n": "{0} succeeded, {1} failed:\n\n",
    "成功 {0} 项，失败 {1} 项：\n\n": "{0} succeeded, {1} failed:\n\n",
    "正在从嘉立创商城刷新 {0} 个元件…": "Refreshing {0} parts from LCSC…",
    "将联网刷新 {0} 个嘉立创元件的资料（型号/厂商/价格等）。\n":
        "This will refresh {0} LCSC parts online (model / manufacturer / price …).\n",
    "元件较多时可能需要一点时间，是否继续？":
        "With many parts this may take a while. Continue?",
    "已刷新 {0} 个元件的商城资料": "Refreshed {0} parts",

    # ---------------------------------------------------------- 删除
    "删除元件": "Delete part",
    "删除该元件": "Delete this part",
    "确认删除": "Confirm delete",
    "已删除": "Deleted",
    "删除失败": "Delete failed",
    "确定要删除元件「{0}」吗？\n": "Delete part \"{0}\"?\n",
    "它的库存记录与出入库流水会一并删除，此操作不可撤销。":
        "Its stock records and transaction history will be deleted too. "
        "This cannot be undone.",
    "库存与流水会一并删除，不可撤销。\n":
        "Stock records and transactions will be deleted too. This cannot be undone.\n",
    "（可在「设置」菜单里关闭这个二次确认）":
        "(you can turn this confirmation off in Settings)",
    "确定删除以下 {0} 个元件吗？\n\n{1}": "Delete these {0} parts?\n\n{1}",

    # ---------------------------------------------------------- 校验与提示
    "填写有误": "Invalid input",
    "格式有误": "Wrong format",
    "缺少信息": "Missing information",
    "保存失败": "Save failed",
    "查询失败": "Query failed",
    "查询失败：{0}": "Query failed: {0}",
    "发生未预期的错误：{0}": "Unexpected error: {0}",
    "请先填写嘉立创 C 号": "Please enter an LCSC C-number first",
    "请填写目标库位": "Please enter the destination location",
    "请先在列表中选择一个元件": "Please select a part in the list first",
    "请先在列表中选择元件": "Please select parts in the list first",
    "还没有从嘉立创商城获取资料，是否仍然保存？\n":
        "LCSC data hasn't been fetched yet. Save anyway?\n",
    "“{0}”不是有效的 C 号，应形如 C1525":
        "\"{0}\" is not a valid C-number; expected a format like C1525",
    "「{0}」必须是数字": "\"{0}\" must be a number",

    # ---------------------------------------------------------- 列表与状态
    "选中一行可查看完整信息；双击行进入编辑。":
        "Select a row to see full details; double-click to edit.",
    "共 {0} 种元件": "{0} part types",
    "筛选出 {0} 种元件（库中共 {1} 种）":
        "{0} parts match (of {1} in library)",
    "已选择 {0} 个元件，将统一执行相同操作":
        "{0} parts selected; the same action applies to all",
    "已选择 {0} 个元件。右键或点下方按钮可批量入库/出库/盘点。":
        "{0} parts selected. Right-click or use the buttons below to act in bulk.",
    "数据库是空的 —— 点右上角「＋ 添加元件」，输入嘉立创 C 号即可自动":
        "Database is empty — click \"＋ Add part\" at the top right and enter an LCSC C-number to",
    "抓取资料；非嘉立创购买的元件点选「其它渠道元件」手工录入。":
        "fetch data; for parts bought elsewhere choose \"Other-channel part\" and enter manually.",
    "数据库：{0}": "Database: {0}",
    "库存 {0}": "Stock {0}",
    "库位 {0}": "Location {0}",
    "分类 {0}": "Category {0}",
    "厂商 {0}": "Manufacturer {0}",
    "封装 {0}": "Package {0}",
    "备注 {0}": "Remark {0}",
    "商城同步 {0}": "LCSC synced {0}",
    "参考单价 ¥{0:.4f}": "Ref. price ¥{0:.4f}",
    "阶梯价 {0}": "Tier prices {0}",
    "　—　表格最多显示 {0} 行，请缩小筛选范围":
        "  —  only the first {0} rows are shown; narrow the filter to see the rest",
    "当前库存 {0}（{1}）　库存变更请用「入库/出库/盘点」":
        "Current stock {0} ({1})　use stock in/out or stocktake to change it",
    "已获取（{0}，{1}）：": "Fetched ({0}, {1}):",
    "{0}　现货 {1} 个": "{0}　in stock: {1}",
    "{0}\n\n你可以切换到「其它渠道元件」手工录入，":
        "{0}\n\nYou can switch to \"Other-channel part\" and enter it manually,",
    "或检查网络后重试。": "or check your connection and try again.",

    # ---------------------------------------------------------- 长句
    # 代码里这些文案写成多行相邻字面量（隐式拼接），key 是拼接后的完整文本
    "　　勾选后数量可以出成负数，并在备注里记下欠账，库存与流水始终一致。":
        "  When enabled the quantity may go negative and the shortfall is noted "
        "in the remark; stock and transactions always stay consistent.",
    "填入 C 号后会自动联网查询（可在「设置」菜单里关闭），"
    "自动带回型号、厂商、封装、价格与数据手册。":
        "Auto-queries online after you type a C-number (can be turned off in "
        "Settings) and retrieves model, manufacturer, package, price and datasheet.",
    "填入 C 号后点「查询商城资料」，自动带回型号、厂商、封装、价格与数据手册。":
        "Enter a C-number and click \"Fetch LCSC data\" to retrieve model, "
        "manufacturer, package, price and datasheet.",
    "将把阈值、操作人、汇率、勾选项全部恢复成出厂默认值。\n"
    "元件资料与库存数据不受影响。是否继续？":
        "This resets threshold, operator, exchange rate and all toggles to "
        "defaults.\nPart data and stock records are not affected. Continue?",
    "支持 Excel（.xls / .xlsx）、CSV、以及网页导出的表格文件。\n"
    "表头会自动识别，常见列名（嘉立创C号 / 商品编号 / 编码 / 型号 / "
    "名称 / 数量 / 购买数量 / 单价 / 采购渠道…）都能直接对上号。":
        "Supports Excel (.xls / .xlsx), CSV and web-exported tables.\n"
        "Headers are detected automatically; common names (LCSC C-No. / part "
        "number / code / model / name / qty / purchase qty / unit price / "
        "supplier …) are all recognized.",
    "数据库是空的 —— 点右上角「＋ 添加元件」，输入嘉立创 C 号即可自动"
    "抓取资料；非嘉立创购买的元件点选「其它渠道元件」手工录入。":
        "Database is empty — click \"＋ Add part\" at the top right and enter an "
        "LCSC C-number to fetch data; for parts bought elsewhere choose "
        "\"Other-channel part\" and enter them manually.",
    "核对上面的「识别列」和下方预览无误后，再点「开始导入」。\n"
    "支持 .xls（Excel 97-2003）、.xlsx、.csv，以及网页导出的表格文件；"
    "表头不在第一行、前面有标题行都没关系。":
        "Check the detected columns above and the preview below, then click "
        "\"Start import\".\nSupports .xls (Excel 97-2003), .xlsx, .csv and tables "
        "exported from web pages; a header that isn't on the first row (with "
        "title rows above) is fine.",
    "每行一个元件，支持 C1525、C1525 100、C1525 x100、"
    "以及立创 BOM 导出的整行文本：":
        "One part per line; accepts C1525, C1525 100, C1525 x100, or full lines "
        "exported from LCSC BOM:",
    "还没有从嘉立创商城获取资料，是否仍然保存？\n"
    "（建议先点「查询商城资料」自动补全信息）":
        "LCSC data hasn't been fetched yet. Save anyway?\n"
        "(click \"Fetch LCSC data\" first to fill in details)",

    # ---------------------------------------------------------- 运行日志与异常兜底
    "打开运行日志": "Open run log",
    "还没有日志文件": "No log file yet",
    "上次运行出现过错误，可点「帮助 → 打开运行日志」查看详情":
        "The previous run reported an error — see Help → Open run log",
    "出错了": "Something went wrong",
    "程序在运行时遇到一个错误，本次操作可能没有完成。\n"
    "详细信息已写入日志文件，反馈问题时请一并提供。\n\n"
    "{0}\n\n日志：{1}":
        "The program hit an error and the last action may not have finished.\n"
        "Details were written to the log file — please include it when reporting.\n\n"
        "{0}\n\nLog: {1}",

    # ---------------------------------------------------------- 语言 / 汇率 / 接入点
    "界面语言": "Interface language",
    "界面文案会立即切换；分类名、库位名属于数据，保持原样":
        "The interface switches immediately; category and location names are "
        "data and stay unchanged",
    "界面语言已切换": "Interface language switched",
    "汇率": "Exchange rate",
    "启动时自动更新": "Update on startup",
    "立即获取": "Fetch now",
    "数据来自公开汇率接口，取不到时沿用上一次的值":
        "Rates come from a public API; the last value is kept if it fails",
    "正在获取汇率…": "Fetching exchange rate…",
    "已更新：1 美元 = {0}（来源 {1}）": "Updated: 1 USD = {0} (source {1})",
    "获取失败：{0}（仍在用上一次的值）":
        "Fetch failed: {0} (still using the last value)",
    "商城接入点": "Marketplace endpoint",
    "自动检测": "Auto-detect",
    "检测会真实查询一次，能取到数据才算可用":
        "A real query is sent; an endpoint counts as usable only if it "
        "returns data",
    "自动（推荐）": "Automatic (recommended)",
    "正在检测…": "Testing endpoints…",
    "检测完成，已选用：{0}": "Done — using: {0}",
    "没有检测到可用的接入点": "No usable endpoint found",
    "检测失败：{0}": "Detection failed: {0}",
    "可用": "available",
}
