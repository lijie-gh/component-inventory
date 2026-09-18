# Component Inventory · 元件库存管理

[简体中文](README.md) | **English**

An electronic component inventory manager for hardware engineers.

> **The app UI itself is bilingual.** Switch to English in
> **Settings → General → UI Language** — it takes effect immediately, no restart.
> The screenshots and menu names below are given in English. Note that
> **the EXE file name is Chinese** (`元件库存管理_v1.0.0_x64.exe`,
> where `元件库存管理` = "component inventory"); the `_x64` / `_x86` suffix is the architecture.

**Highlights**

- Enter a **JLCPCB / LCSC part number (C-number)** and the part data is fetched automatically —
  MPN, manufacturer, package, category, reference price, datasheet link
- Parts bought **elsewhere** (Taobao, local markets, salvaged boards…) can be added just as easily
  through the "other source" manual entry, and filtered out separately in the list
- Stock in/out, stocktaking and storage-location transfers are fully logged — searchable and exportable
- **UI in Chinese or English**, exchange rate **fetched online automatically**, shop API endpoint
  **chosen automatically**
- A single EXE file — **no installation, just double-click**. Your data sits right next to it,
  so copying the folder copies everything

---

## 1. Quick Start

### 1.1 Download

Grab the file from the **[Releases](../../releases)** page — pick the build that matches your system:

| Download | For | Notes |
|---|---|---|
| **`元件库存管理_v1.0.0_x64.exe`** | 64-bit Windows | virtually every PC — prefer this one |
| **`元件库存管理_v1.0.0_x86.exe`** | 32-bit Windows | older machines; also runs on 64-bit Windows |

Both builds have **identical features and UI** — the difference is only the bitness they were
compiled for.

Not sure which one you need? See the next section.

### 1.2 Launching it

Put it in any folder you like (a USB stick works too) and **double-click** it.

- The single-file EXE has to unpack itself on first launch — about **3–5 seconds**, faster afterwards
- The main window opens straight away; nothing is installed, nothing is written to the registry

### 1.3 Where your data lives

The app creates a `data\` folder **next to the EXE**:

```
data\
├── inventory.db     ← all of your parts and stock live in this one file
├── settings.json    settings (UI language, warning threshold, exchange rate, checkboxes)
└── backup\          database backups
```

That means you can copy the whole folder onto a USB stick or another PC and carry on working —
no configuration to change.

> **Do not drag the EXE out on its own** — it will treat its new folder as an empty warehouse.
> Move the whole folder together.
>
> If you place the folder somewhere that **requires administrator rights**
> (such as `C:\Program Files`), the app falls back to storing data in
> `%APPDATA%\元件库存管理\` automatically. It keeps working normally either way.

### 1.4 Antivirus warnings

A single-file EXE is essentially a self-extracting program, and some antivirus tools are sensitive
about them. Add it to your whitelist if needed — the full source is in the ZIP next to it on the
releases page, so you can check for yourself.

---

## 2. Which Build Should I Download?

| | `元件库存管理_v1.0.0_x64.exe` | `元件库存管理_v1.0.0_x86.exe` |
|---|---|---|
| Runs on | 64-bit Windows | 32-bit Windows; also 64-bit Windows |
| File size | about 10 MB | about 8.8 MB |
| Features | identical | identical |

**How to choose:**

- Windows 10 / 11 is almost always 64-bit → take **`x64`**
- **If in doubt, take `x86`** — a 32-bit program **always** runs on 64-bit Windows
  (the system provides a WOW64 compatibility layer); the reverse is not true
- To check your own system: right-click **This PC** on the desktop → **Properties** →
  look at "System type"

**What picking the wrong one looks like:** on double-click you get
*"is not a valid Win32 application"*. The download is not corrupted and antivirus is not involved —
just swap it for the other build.

**Two other common launch problems:**

| Symptom | Cause and fix |
|---|---|
| *"Windows protected your PC"* | The program has no paid code-signing certificate; this is the usual prompt for unsigned software. Click **More info** → **Run anyway** |
| Double-click does nothing | Give it a few seconds (the first unpack is slow). If no window ever appears, check whether your security software blocked it silently |

> As a 32-bit process the `x86` build can address roughly 2 GB of memory. An inventory of this kind
> will never come close to that, so normal use is indistinguishable between the two.

---

## 3. UI Language, Exchange Rate and API Endpoint

All three live in **Settings → General Settings** (shortcut `Ctrl+,`).

### 3.1 UI language (Chinese / English)

The top of the settings window has a **UI Language** dropdown. Pick **English**, click **Save**, and
the menus, column headers, buttons and messages switch **immediately** — **no restart**.

- Chinese is the native language; anything missing from the English dictionary
  **falls back to Chinese** rather than showing blanks or throwing an error
- Part data (MPN, manufacturer, category, parameter values) plus your own remarks and
  storage-location names are **data** and are never translated — only the UI is
- You can also edit the config file directly: the `language` field (`zh` / `en`) in
  `data\settings.json`

### 3.2 Automatic exchange rate

JLCPCB's international shop quotes in **US dollars**, and the app converts to CNY using a
**live rate fetched online**:

- 1.5 seconds after launch it updates once in the background (the UI never freezes);
  it will not request again for 12 hours
- Click **Fetch Now** in the settings window to refresh manually; a status line such as
  `1 USD = 6.7218 CNY (open.er-api.com, 2026-09-18 00:20)` is shown alongside
- If the network is unavailable the last known value is reused; if it has never been fetched,
  the offline fallback of 7.2 is used (and can be edited by hand)
- To pin a fixed rate: untick **Update exchange rate on startup** and type your own value

> Changing the rate does **not** automatically recalculate prices already stored.
> Select the parts and right-click → **Refresh data from JLCPCB** to update them.

### 3.3 Automatic API endpoint detection

JLCPCB part lookup is available through several endpoints, and availability varies a lot by region
and network. The app **probes them concurrently** and automatically picks the fastest one that
**actually returns data**:

| Endpoint | Notes |
|---|---|
| JLCPCB international `jlcpcb.com` | the working main endpoint today |
| JLCPCB domestic `szlcsc.com` | fast inside China, but the API is not open to third-party apps and returns nothing |
| LCSC international `lcsc.com` | blocked on some networks |

- It runs once automatically after the first launch; the result shows in the **Endpoint** row of the
  settings window
- You can click **Auto-detect** to test again, or **lock** a specific endpoint in the dropdown
- **Detection is not just a latency test**: it performs a real query (using `C1525`, a resistor),
  and only counts an endpoint as usable if data comes back. Otherwise you would end up with
  "the domestic endpoint has the lowest ping but returns nothing"

> Probing runs on a background thread and gives up after a few seconds when offline; the app stays
> fully usable — you just cannot auto-fill part data. Manual entry, stock in/out and everything else
> keep working.

---

## 4. Adding Parts

### 4.1 Parts bought from JLCPCB

1. Click **+ Add Part** in the top-right corner
2. Keep **JLCPCB part (enter a C-number to fetch data automatically)** selected
3. Type a part number such as `C1525` into the C-number box — it is **looked up automatically**
   after a moment (or press Enter / click **Look up part data**)
4. The app fills in: name/description, MPN, manufacturer, package, category, parameter values,
   a **localised description**, supplier channel, reference price and the datasheet link
5. Enter a **quantity** and a **storage location** → click **Save**

> - The leading `C` is optional: `1525`, `c1525` and `C1525` all work
> - Entering the same C-number twice does **not** create a duplicate record — the quantity is
>   simply added to existing stock
> - Lookup results are cached for 7 days, so repeat lookups do not hit the network;
>   expired cache entries are pruned at startup
> - The description is localised into Chinese; the original English text is shown in small print
>   just below the description box (see the FAQ)
> - The reference price is converted from USD using the rate described in section 3; if the network
>   is unavailable, the fallback value from settings (7.2) is used
> - The app stores the **entire price-tier table**, and the stock value is computed from the tier
>   that matches the current quantity (see section 7)
> - To stop the automatic lookup, turn off **Look up part data automatically when adding a part**
>   in **Settings**

### 4.2 Parts bought elsewhere

1. Click **+ Add Part**
2. Switch to **Other source (not bought from JLCPCB — manual entry)**
3. Fill in name/description, MPN, supplier channel (e.g. "Taobao"), package, quantity … no network
   access at all
4. Click **Save**

These parts show **Other source** in the Source column of the list.

---

## 5. Filtering and Search

This is the core of managing JLCPCB parts and non-JLCPCB parts side by side.

| Filter | Options | Purpose |
|---|---|---|
| Source | All / **JLCPCB only** / **Other source only** | Pull out the parts bought elsewhere |
| Stock | All / In stock / Zero stock / **Low-stock warning** | Find what is running out or already gone |
| Category | Resistors, capacitors, MCUs… | Browse by type |

- The search box matches C-number, MPN, name, manufacturer, package, parameter values,
  **storage location** and remarks — filtering as you type
- Click any column header to sort; click again to reverse the order
- The **Filter** menu offers the same controls for one-click switching

---

## 6. Stock In / Stock Out

Select one or more parts in the list (`Ctrl` to multi-select, `Shift` for a range), then:

| Action | Description |
|---|---|
| **Stock in** | Increase stock (newly purchased parts) |
| **Stock out** | Decrease stock; refused if there is not enough, so stock never goes negative |
| **Stocktake** | **Overwrite** a location's quantity with the counted value; the difference is logged automatically |
| **Transfer** | Move quantity between two storage locations; the total is unchanged |

Every action accepts an operator and a remark. All movements are recorded in a log you can view
under **Help → Stock movement log**, and export to CSV separately.

> **Stock and log always agree.** The quantity change and the log entry are a single write; a power
> failure or crash rolls both back, so you can never end up with "stock went down but nobody knows
> who took it".
>
> **Negative stock (optional).** By default a stock-out larger than the quantity on hand is refused.
> If you prefer "take the parts now, register them later", tick
> **Allow negative stock** in the stock-out dialog, or enable it by default in Settings.
> The quantity is then genuinely stored as negative and the log records how many are owed —
> stock and log still reconcile.

---

## 7. How the Stock Value Is Calculated

JLCPCB prices in **tiers**: 1 piece, 1000 pieces and 10000 pieces all cost different amounts per
unit, cheaper in larger quantities.

The app stores the **entire price-tier table** and then:

- **Reference price (by qty)** column = the tier price matching the **current stock quantity**
- **Stock value** column = quantity × that tier price

A real example (C5369112):

| Tier | Unit price |
|---|---|
| 1+ | $0.0188 |
| 500+ | $0.0146 |
| 2000+ | $0.0123 |
| 50000+ | $0.0091 |

With 600 in stock it uses the **500+ tier**: 0.0146 × 6.72 (live rate) = **¥0.0981 each**,
so the stock value is 600 × 0.0981 = **¥58.86**.

> Because both columns use the same basis, **quantity × reference price always equals the stock
> value** — you can verify it by hand.
> Items with zero stock have no tier to match, so the single-piece list price is shown.
>
> Manually entered parts (other source) have no tier table and use the reference price you typed.
>
> To bring earlier parts onto tier pricing, select them and right-click →
> **Refresh data from JLCPCB**.

---

## 8. Batch Import

Click **Batch import** (also in the **File** menu). There are two tabs:

### 8.1 Paste C-numbers / a BOM list

One per line; these forms are all understood:

```
C1525 100
C1525 x100
C1525,100
1  C1525  100nF  0402  100      ← a full row exported from an LCSC BOM works too
```

Repeating the same C-number on one line adds the quantities together.

### 8.2 Import from an Excel / CSV file

Supports **`.xls` (Excel 97-2003)**, **`.xlsx`**, **`.csv`**, and web-exported tables that merely
pretend to be `.xls`. **Excel and extra plugins are not required on your machine.**

1. Click **Browse…** and pick a file. The app shows what it recognised, then a preview —
   confirm before importing
2. If the workbook has several sheets (e.g. "order info + item details"), a **Sheet** dropdown
   appears, defaulting to the one with the most rows; switch any time
3. Column headers are detected automatically; these names are all recognised:

| Field | Common column names |
|---|---|
| C-number | 嘉立创C号, C号, 商品编号, 商品编码, 立创编号, 元件编号, 物料编码, 编码… |
| MPN | 型号, 规格型号, 商品型号, 制造商编号, MPN |
| Name | 名称, 商品名称, 元件名称, 描述, 名称/描述 |
| Manufacturer | 厂商, 品牌, 制造商, 生产厂商 |
| Package | 封装, 封装形式, Package |
| Quantity | 数量, 购买数量, 下单数量, 采购数量, 库存总数, 订货数量 |
| Unit price | 单价, 采购单价, 商品单价, 含税单价, 参考单价 |
| Location | 库位, 位置, 存放位置 |

Title rows above the header are fine (the app looks further down); if no header can be identified
at all it guesses by content (which column looks like a C-number, which looks like a quantity) and
asks you to check the preview.

**Two checkboxes:**

- **For existing parts, only append stock — do not overwrite recorded data** (on by default)
  Use this when importing purchase records repeatedly: quantities accumulate, while categories,
  remarks and warning thresholds you have edited by hand are not wiped out by empty cells
- **Fetch JLCPCB data for newly created parts** (on by default)
  New C-numbers not yet in the list are looked up for a description, category and live price.
  For very large imports or offline work, untick it to create the records from the spreadsheet
  alone, then click **Refresh shop data for selected parts** afterwards

> Date columns (such as "order date") are read as `2026-09-01`, not as a serial number like 45123.
> Formula cells contribute their computed value.

---

## 9. Export and Backup

- **File → Export full list to CSV** / **Export current filter result** — opens directly in Excel,
  no mojibake with Chinese text
- **File → Export stock movement log** — the complete record of movements
- **File → Back up database** — copies the database into `data\backup\` with a timestamped name
- Exported CSVs go into the `导出\` folder by default

> The backup takes a **consistent snapshot** of the database, so even while the app is running and
> writing in the background, the file you get is complete and usable — never a half-old,
> half-new mixture. Worth doing regularly, and before any big change.

---

## 10. Moving to Another PC and Data Safety

### Moving to another PC / a USB stick

Copy the **whole folder** (the EXE plus `data\`). All paths are derived relatively — there is no
configuration to change.

### Back up regularly

Use **File → Back up database**; backups land in `data\backup\`.
The database is a **single file**, `data\inventory.db`, so simply copying it works too as an offline
safety copy (close the app first, ideally).

### What the app does online

The app **collects and uploads nothing** — no account, no telemetry, no cloud sync.

Only three things ever touch the network, and each can be turned off or controlled manually in
Settings:

| When | What goes online |
|---|---|
| Looking up / refreshing part data | Querying JLCPCB for that C-number's public data |
| At startup, or when you click **Fetch Now** | Fetching the USD exchange rate |
| First launch, or when you click **Auto-detect** | Probing which shop endpoint is reachable |

Offline, none of the above matters: manual entry, stock in/out, filtering, exporting and backup all
work normally.

### Where your data is

`data\inventory.db` is a standard SQLite file and your only asset — deleting the app does not touch
it, and deleting it loses everything. Back it up before moving machines or reinstalling Windows.

---

## 11. FAQ

**Q: Where are the settings?**

The menu bar has a dedicated **Settings** tab (there is also a **⚙ Settings** button at the right end
of the toolbar):

- **General Settings…** (`Ctrl+,`) — UI language, low-stock warning threshold, default operator,
  USD exchange rate (with **Fetch Now**), shop endpoint (with **Auto-detect**)
- **Look up part data automatically when adding a part** — with this ticked, typing a C-number
  fetches the data for you
- **Confirm before deleting a part** — turn it off and Delete removes instantly; use with care
- **Clear shop data cache** / **Open data folder**
- **Restore default settings…** — resets the above to factory values, **without touching parts or
  stock data**

Settings live in `data\settings.json`; deleting that file also restores the defaults.

**Q: How do I switch the UI to English?**

**Settings → General Settings**, choose **English** in the **UI Language** dropdown at the top.
It takes effect the moment you save — no restart. You can also edit `"language": "en"` in
`data\settings.json` directly (see section 3).

**Q: Is the exchange rate automatic? Can I pin my own value?**

It is automatic — shortly after launch the app fetches a live rate in the background
(e.g. 1 USD = 6.72 CNY) and will not repeat the request for 12 hours; click **Fetch Now** in
Settings to refresh manually.
To pin a value: untick **Update exchange rate on startup** and type your own rate (see section 3).

**Q: It says "cannot connect to JLCPCB"?**

Either the network is down or the shop API is temporarily unavailable. In
**Settings → General Settings → Endpoint**, click **Auto-detect** to see whether the current
endpoint is unreachable and whether another one works.
Manual entry and stock in/out are unaffected — you just cannot auto-fill part data.
If your company network uses a proxy, it has to be configured in the system environment variables.

**Q: A C-number lookup says "not found in shop"?**

Double-check the number. Some discontinued or non-standard parts are absent from the shop's SMT
library; for those, switch to **Other source** and enter the part manually.

**Q: Why is the detailed description all in English?**

The app queries JLCPCB's **international** SMT library, whose raw data is English only.
(The domestic site has Chinese data, but its API is not open to third-party programs.)

The app ships with a component terminology dictionary that localises the English attribute table
into Chinese, for example:

```
English  Termination Style = Gull Wing | Circuit = SPST | Life = 100,000 Cycles
Chinese  端子形式：鸥翼引脚 | 电路：单刀单掷 | 寿命：10万次
```

Values and units (12V, 100nF, 4.5mm) are preserved verbatim — nothing is converted and no part
number is ever mangled. The original English is shown in small print under the description box for
reference.

If a word is missing from the dictionary you can add it yourself — edit
`data\i18n_custom.json` (create the file if it does not exist):

```json
{
  "属性名": { "Voltage Rating": "额定电压" },
  "值":     { "Gull Wing": "鸥翼引脚" },
  "类型":   { "Tactile Switches": "轻触开关" }
}
```

Restart the app for the change to take effect.

**Q: The reference price does not match the shop page?**

The international shop quotes in **USD** and the app converts at the live rate
(e.g. 1 USD = 6.72 CNY), so the number is several times larger — that is expected.
You can pin a fixed rate; after changing it, refresh the part data to update stored prices.

On top of that, **Reference price (by qty) shows the tier price for the current stock quantity**,
not the single-piece price. If a part costs ¥0.1263 at 1+ and ¥0.0981 at 500+, then the column shows
0.1263 with 300 in stock and 0.0981 with 600 in stock, and the stock value follows
(see section 7). This is what makes quantity × price equal the value — it is not a bug.

If you only want the single-piece list price, set the quantity to 1 and read that column, or check
the shop page.

**Q: The stock value is not what I estimated?**

Check these first:

1. **It uses tier pricing** — the value uses the tier price for the current quantity, which is well
   below the single-piece price
2. **Parts only** — taxes, shipping, PCBs and enclosures are not included
3. **Manually entered parts have no tiers** — they use the reference price you typed, so put in a
   reasonable figure
4. **Old data was not recalculated** — after changing the rate, or to benefit from tier pricing,
   select the parts and right-click → **Refresh data from JLCPCB**

**Q: How should I set the low-stock warning threshold?**

Set a global threshold in **Settings → General Settings** (default 10). Individual parts can carry
their own **warning threshold** in the edit dialog, which takes precedence.
Rows below the threshold turn orange in the list; zero stock turns red.

The **Low-stock warning** card on the dashboard **excludes zero stock** — those are counted on the
**Zero stock** card instead, so the two numbers never double-count, and
"low stock + zero stock" is exactly the number of part types needing replenishment.

**Q: My purchase records are `.xls`. Can I import them?**

Yes. Use **Batch import → Import from Excel / CSV file** and keep the default file type
("Excel / CSV tables") to see `.xls` files. The app reads the real content rather than trusting the
extension: genuine binary Excel, xlsx, web-exported tables and CSV all work. If one particular file
fails, re-saving it as `.xlsx` or `.csv` in Excel usually fixes it.

**Q: Can I open the database with another tool?**

Yes, it is a standard SQLite file — open `data\inventory.db` with something like DB Browser for
SQLite.

**Q: The UI font / scaling looks wrong?**

Change the scaling factor in Windows display settings, then restart the app.

**Q: Do I have to use the EXE? Can I just run the source?**

Yes. The ZIP on the releases page contains the complete source; unzip it and double-click
**`启动程序.bat`** (you need Python 3.7 or newer installed, with `tcl/tk and IDLE` selected during
installation — the official installer ticks it by default). It behaves exactly like the EXE, and
your data also lands next to the program.

---

## License

No open-source licence is attached. The code is provided for reference and personal use.
