# Personal Finance Pro

Private, offline personal finance manager for Windows. Data stays on your computer in a local SQLite database
(`%USERPROFILE%\.personal_finance_lite\finance.db`) — the same folder as Personal Finance Lite, so your existing
data appears automatically.

## What's new in Pro
- **Smooth, animated UI** — count-up KPI cards, growing charts, fade transitions between tabs, toast notifications
- **Interactive dashboard** — hover the bar chart and the donut for details, trend badges vs the previous period,
  daily average and projected month-end spending, right-click any chart to save it as PNG
- **Export centre (Ctrl+E)** — choose *current view / selected rows / everything* and a format:
  - **Excel (.xlsx)** — Summary, Transactions, By Category and Monthly sheets with live formulas, filters, native charts
  - **PDF report** — KPIs, charts, category breakdown, largest expenses, full transaction list
  - **CSV** — re-importable; **JSON** — transactions + budgets + summary
  - Copy rows straight to the clipboard (paste into Excel / Google Sheets)
- **Undo (Ctrl+Z)** for add, edit, duplicate, delete and clear-all, plus an *Undo* button on the toast
- **Recurring transactions** — monthly rent, salary, subscriptions; missed months are filled in on start-up
- **Dark / light theme** (Ctrl+Shift+T), remembered between sessions; window size and position are remembered too
- Right-click menu on transactions, *Save & add another*, live selection totals, debounced search,
  drag-and-drop a `.csv` file onto the window to import it, budget warnings the moment you overspend

## Shortcuts
`Ctrl+N` add · `Ctrl+E` export · `Ctrl+Z` undo · `Ctrl+F` search · `Ctrl+1/2/3` switch tab ·
`Ctrl+Shift+T` theme · `F5` refresh · `Del` delete selected · `Ctrl+C` copy selected rows · `Enter` edit selected

## Run / build
- Run from source: `pip install -r requirements.txt` then `python main.py` (or `Run Personal Finance Pro.bat`)
- Build the EXE: `Build EXE.bat` → `release\Personal Finance Pro.exe`
- Build the installer (needs Inno Setup 6): `Build Installer.bat`

## Safety
Automatic daily backups (last 15 kept), manual backup, one-click restore, and an automatic safety copy before
clear / import / restore.
