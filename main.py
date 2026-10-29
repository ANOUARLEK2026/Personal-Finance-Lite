import html
import math
import sys
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import (
    Qt, QDate, QSize, QRectF, QPointF, QMarginsF, QUrl, QTimer, QSettings,
    QVariantAnimation, QPropertyAnimation, QEasingCurve, QAbstractAnimation,
)
from PySide6.QtGui import (
    QFont, QColor, QAction, QIcon, QPixmap, QImage, QPainter, QPen, QKeySequence,
    QShortcut, QDesktopServices, QTextDocument, QPdfWriter, QPageSize, QPageLayout,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QMessageBox, QFrame, QHeaderView,
    QTabWidget, QDialog, QFileDialog, QAbstractItemView, QProgressBar,
    QStatusBar, QSplashScreen, QMenu, QScrollArea, QCheckBox, QToolTip,
    QGraphicsOpacityEffect,
)

import core
from core import APP_NAME, APP_VERSION, CATEGORIES, money

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------
DARK = dict(
    name="dark", bg="#0b1220", panel="#111b2e", panel2="#152238", border="#22314a", border2="#31425f",
    text="#e5e7eb", strong="#f8fafc", muted="#94a3b8", input="#0a1322", hover="#223555",
    btn="#18263d", btnborder="#2b3d59", select="#243b61", table="#0e1727", alt="#111d31",
    grid="#22314a", accent="#2563eb", accent_h="#3b82f6", green="#4ade80", red="#fb7185",
    blue="#60a5fa", purple="#a78bfa", amber="#f59e0b", tab_sel="#16243a", icon="#dce9ff",
    danger_bg="#451b25", danger_bd="#7f1d2d", danger_tx="#fecdd3", danger_h="#5b202c",
    toast="#1e2d4a", card_a="#152238", card_b="#101a2b",
)
LIGHT = dict(
    name="light", bg="#f1f5f9", panel="#ffffff", panel2="#f8fafc", border="#e2e8f0", border2="#cbd5e1",
    text="#1e293b", strong="#0f172a", muted="#64748b", input="#ffffff", hover="#e2e8f0",
    btn="#ffffff", btnborder="#cbd5e1", select="#dbeafe", table="#ffffff", alt="#f8fafc",
    grid="#e2e8f0", accent="#2563eb", accent_h="#1d4ed8", green="#16a34a", red="#e11d48",
    blue="#2563eb", purple="#7c3aed", amber="#d97706", tab_sel="#e2e8f0", icon="#334155",
    danger_bg="#ffe4e6", danger_bd="#fda4af", danger_tx="#9f1239", danger_h="#fecdd3",
    toast="#0f172a", card_a="#ffffff", card_b="#f8fafc",
)
T = dict(DARK)  # the active palette (mutated in place so every widget sees changes)


def set_theme(name):
    T.clear()
    T.update(LIGHT if name == "light" else DARK)


SLICE_COLORS = ["#60a5fa", "#4ade80", "#fbbf24", "#fb7185", "#a78bfa", "#22d3ee", "#f97316", "#94a3b8"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def resource_path(relative):
    """Return a resource path for both source mode and a PyInstaller bundle."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / relative)


def app_icon(name, color=None):
    """Load an SVG icon and tint it so it stays visible in both themes."""
    pm = QIcon(resource_path(f"assets/{name}.svg")).pixmap(QSize(48, 48))
    if pm.isNull():
        return QIcon()
    painter = QPainter(pm)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pm.rect(), QColor(color or T["icon"]))
    painter.end()
    return QIcon(pm)


def make_button(text, icon=None, name=None, tip=None, slot=None, icon_color=None):
    btn = QPushButton(text)
    if icon:
        btn.setIcon(app_icon(icon, icon_color))
        btn.setIconSize(QSize(18, 18))
    if name:
        btn.setObjectName(name)
    if tip:
        btn.setToolTip(tip)
    if slot:
        btn.clicked.connect(slot)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def short_money(v):
    a = abs(v)
    if a >= 1e6:
        return f"{v / 1e6:.1f}M"
    if a >= 1e3:
        return f"{v / 1e3:.0f}k"
    return f"{v:.0f}"


def nice_ceiling(v):
    if v <= 0:
        return 1.0
    exp = 10 ** math.floor(math.log10(v))
    frac = v / exp
    for step in (1, 2, 2.5, 5, 10):
        if frac <= step:
            return step * exp
    return 10 * exp


def make_bar(spent, budget):
    """Progress bar for spending against a budget (turns amber at 80%, red when over)."""
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setTextVisible(True)
    if budget > 0:
        pct = int(round(spent / budget * 100))
        bar.setValue(min(pct, 100))
        bar.setFormat(f"{pct}%")
        bar.setProperty("state", "over" if pct > 100 else "warn" if pct >= 80 else "ok")
    else:
        bar.setValue(0)
        bar.setFormat("No budget")
    return bar


class NumericItem(QTableWidgetItem):
    """Table item that sorts by a number stored in Qt.UserRole instead of by its text."""

    def __lt__(self, other):
        try:
            return float(self.data(Qt.ItemDataRole.UserRole)) < float(other.data(Qt.ItemDataRole.UserRole))
        except (TypeError, ValueError):
            return super().__lt__(other)


# ---------------------------------------------------------------------------
# Toast notifications (non-blocking feedback with optional action button)
# ---------------------------------------------------------------------------
class Toast(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 10, 10, 10)
        lay.setSpacing(12)
        self.label = QLabel()
        self.label.setObjectName("toastText")
        self.button = QPushButton()
        self.button.setObjectName("toastAction")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self._clicked)
        close = QPushButton("✕")
        close.setObjectName("toastClose")
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.fade_out)
        lay.addWidget(self.label)
        lay.addWidget(self.button)
        lay.addWidget(close)

        self.effect = QGraphicsOpacityEffect(self)
        self.effect.setOpacity(0.0)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity", self)
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.finished.connect(self._finished)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)
        self.callback = None
        self._hiding = False
        self.hide()

    def show_message(self, text, action=None, callback=None, ms=5500, kind="info"):
        self.label.setText(text)
        self.callback = callback
        self.button.setVisible(bool(action))
        if action:
            self.button.setText(action)
        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)
        self._hiding = False
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._fade(1.0)
        self.timer.start(ms)

    def _fade(self, target):
        self.anim.stop()
        self.anim.setStartValue(self.effect.opacity())
        self.anim.setEndValue(target)
        self.anim.start()

    def fade_out(self):
        self._hiding = True
        self._fade(0.0)

    def _finished(self):
        if self._hiding:
            self.hide()

    def _clicked(self):
        cb, self.callback = self.callback, None
        self.fade_out()
        if cb:
            cb()

    def reposition(self):
        p = self.parentWidget()
        if p:
            self.move(max((p.width() - self.width()) // 2, 8), p.height() - self.height() - 48)


# ---------------------------------------------------------------------------
# KPI card with animated count-up and a "vs previous period" badge
# ---------------------------------------------------------------------------
class StatCard(QFrame):
    def __init__(self, title, accent="blue", fmt=money, good_when_up=True):
        super().__init__()
        self.setObjectName("statCard")
        self.setProperty("accent", accent)
        self.fmt = fmt
        self.good_when_up = good_when_up
        self._value = 0.0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 13)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("statTitle")
        self.value_label = QLabel(fmt(0))
        self.value_label.setObjectName("statValue")
        self.delta_label = QLabel(" ")
        self.delta_label.setObjectName("statDelta")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.delta_label)
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(650)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._tick)

    def _tick(self, v):
        self._value = float(v)
        self.value_label.setText(self.fmt(self._value))

    def set_value(self, value, delta=None, animate=True):
        self.anim.stop()
        if animate:
            self.anim.setStartValue(float(self._value))
            self.anim.setEndValue(float(value))
            self.anim.start()
        else:
            self._tick(value)
        if delta is None:
            self.delta_label.setText(" ")
            return
        up = delta >= 0
        good = up == self.good_when_up
        color = T["green"] if good else T["red"]
        arrow = "▲" if up else "▼"
        self.delta_label.setStyleSheet(f"color:{color};background:transparent;font-size:11px;font-weight:600;")
        self.delta_label.setText(f"{arrow} {abs(delta):.1f}% vs previous period")


# ---------------------------------------------------------------------------
# Charts (QPainter, no extra dependency). Animated, hoverable, exportable.
# ---------------------------------------------------------------------------
class AnimatedChart(QWidget):
    def __init__(self):
        super().__init__()
        self.progress = 1.0
        self.hover = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(200)
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(700)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._set_progress)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def _set_progress(self, v):
        self.progress = float(v)
        self.update()

    def play(self):
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def draw(self, p, w, h, pal, progress, hover):  # pragma: no cover - implemented by subclasses
        raise NotImplementedError

    def paintEvent(self, _event):
        p = QPainter(self)
        self.draw(p, self.width(), self.height(), T, self.progress, self.hover)
        p.end()

    def leaveEvent(self, _event):
        if self.hover != -1:
            self.hover = -1
            self.update()
        QToolTip.hideText()

    def to_image(self, w, h, pal):
        img = QImage(w * 2, h * 2, QImage.Format.Format_ARGB32)
        img.setDevicePixelRatio(2)
        img.fill(QColor(pal["panel"]))
        p = QPainter(img)
        self.draw(p, w, h, pal, 1.0, -1)
        p.end()
        return img

    def _menu(self, pos):
        menu = QMenu(self)
        save = menu.addAction("Save chart as PNG…")
        copy = menu.addAction("Copy chart to clipboard")
        chosen = menu.exec(self.mapToGlobal(pos))
        img = self.to_image(max(self.width(), 480), max(self.height(), 220), T)
        if chosen == save:
            path, _ = QFileDialog.getSaveFileName(self, "Save chart", str(Path.home() / "chart.png"), "PNG image (*.png)")
            if path:
                img.save(path if path.lower().endswith(".png") else path + ".png")
        elif chosen == copy:
            QApplication.clipboard().setImage(img)


class MonthlyChart(AnimatedChart):
    """Income vs expenses per month: [(label, income, expense)]."""

    def __init__(self):
        super().__init__()
        self.data = []

    def set_data(self, data, animate=True):
        self.data = data
        self.hover = -1
        if animate:
            self.play()
        else:
            self.progress = 1.0
            self.update()

    def _geometry(self, w, h):
        left, right, top, bottom = 46, 10, 30, 24
        return left, right, top, bottom, h - bottom, h - bottom - top

    def draw(self, p, w, h, pal, progress, hover):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, right, top, bottom, baseline, plot_h = self._geometry(w, h)
        muted = QColor(pal["muted"])
        p.setFont(QFont("Segoe UI", 9))

        x = left
        for color, label in ((pal["green"], "Income"), (pal["red"], "Expenses")):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(x, 8, 10, 10), 3, 3)
            p.setPen(muted)
            p.drawText(QRectF(x + 15, 4, 70, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            x += 90

        peak = max((max(i, e) for _, i, e in self.data), default=0)
        if not self.data or peak <= 0:
            p.setPen(QPen(QColor(pal["grid"]), 1))
            p.drawLine(left, baseline, w - right, baseline)
            p.setPen(muted)
            p.drawText(QRectF(0, top, w, plot_h), Qt.AlignmentFlag.AlignCenter, "No data yet")
            return
        peak = nice_ceiling(peak)

        for i in range(3):
            y = baseline - plot_h * i / 2
            p.setPen(QPen(QColor(pal["grid"]), 1, Qt.PenStyle.SolidLine if i == 0 else Qt.PenStyle.DashLine))
            p.drawLine(left, int(y), w - right, int(y))
            p.setPen(muted)
            p.drawText(QRectF(0, y - 9, left - 6, 18),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, short_money(peak * i / 2))

        slot = (w - left - right) / len(self.data)
        bar_w = max(6.0, min(26.0, slot * 0.28))
        for idx, (label, income, expense) in enumerate(self.data):
            cx = left + slot * idx + slot / 2
            if idx == hover:
                hl = QColor(pal["hover"])
                hl.setAlpha(110)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(hl)
                p.drawRoundedRect(QRectF(cx - slot / 2 + 3, top - 4, slot - 6, plot_h + 4), 8, 8)
            for offset, value, color in ((-bar_w - 1, income, pal["green"]), (1, expense, pal["red"])):
                bh = value / peak * plot_h * progress
                if bh <= 0:
                    continue
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(cx + offset, baseline - bh, bar_w, bh), 3, 3)
            p.setPen(QColor(pal["strong"]) if idx == hover else muted)
            p.drawText(QRectF(cx - slot / 2, baseline + 4, slot, 18), Qt.AlignmentFlag.AlignCenter, label)

    def mouseMoveEvent(self, event):
        if not self.data:
            return
        left, right, *_ = self._geometry(self.width(), self.height())
        slot = (self.width() - left - right) / len(self.data)
        x = event.position().x()
        idx = int((x - left) // slot) if left <= x <= self.width() - right else -1
        idx = idx if 0 <= idx < len(self.data) else -1
        if idx != self.hover:
            self.hover = idx
            self.update()
        if idx >= 0:
            label, inc, exp = self.data[idx]
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"<b>{html.escape(label)}</b><br>Income: {money(inc)}<br>Expenses: {money(exp)}<br>Net: <b>{money(inc - exp)}</b>",
                self,
            )
        else:
            QToolTip.hideText()


class DonutChart(AnimatedChart):
    """Spending split by category: [(name, amount)] sorted descending."""

    def __init__(self):
        super().__init__()
        self.data = []

    def set_data(self, data, animate=True):
        data = [(n, float(v)) for n, v in data if v > 0]
        if len(data) > 7:  # fold the long tail into one slice so the legend stays readable
            data = data[:7] + [("Others", sum(v for _, v in data[7:]))]
        self.data = data
        self.hover = -1
        if animate:
            self.play()
        else:
            self.progress = 1.0
            self.update()

    def _geometry(self, w, h):
        legend_w = 150 if w >= 340 else 0
        d = min(h - 20, w - legend_w - 24)
        d = max(d, 60)
        cx, cy = 12 + d / 2, h / 2
        return cx, cy, d, d * 0.17, 12 + d + 18, legend_w

    def draw(self, p, w, h, pal, progress, hover):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        muted = QColor(pal["muted"])
        total = sum(v for _, v in self.data)
        cx, cy, d, th, lx, legend_w = self._geometry(w, h)
        if total <= 0:
            p.setPen(QPen(QColor(pal["grid"]), th))
            p.drawArc(QRectF(cx - d / 2 + th / 2, cy - d / 2 + th / 2, d - th, d - th), 0, 360 * 16)
            p.setPen(muted)
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(QRectF(cx - d / 2, cy - 10, d, 20), Qt.AlignmentFlag.AlignCenter, "No expenses")
            return

        gap = 1.6 if len(self.data) > 1 else 0
        start = 90.0
        for i, (_, value) in enumerate(self.data):
            span = value / total * 360 * progress
            thick = th + (5 if i == hover else 0)
            pen = QPen(QColor(SLICE_COLORS[i % len(SLICE_COLORS)]), thick, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
            p.setPen(pen)
            inset = thick / 2
            rect = QRectF(cx - d / 2 + inset, cy - d / 2 + inset, d - thick, d - thick)
            draw_span = max(span - gap, 0.2)
            p.drawArc(rect, int(start * 16), int(-draw_span * 16))
            start -= span

        # centre label
        if 0 <= hover < len(self.data):
            name, value = self.data[hover]
            title, big, small = name, short_money(value), f"{value / total * 100:.1f}%"
        else:
            title, big, small = "Expenses", short_money(total), "total"
        inner = d - th * 2 - 6
        fm_big = QFont("Segoe UI", 13, QFont.Weight.Bold)
        p.setPen(muted)
        p.setFont(QFont("Segoe UI", 8))
        fm = QFontMetrics(p.font())
        p.drawText(QRectF(cx - inner / 2, cy - 26, inner, 16), Qt.AlignmentFlag.AlignCenter,
                   fm.elidedText(title, Qt.TextElideMode.ElideRight, int(inner)))
        p.setPen(QColor(pal["strong"]))
        p.setFont(fm_big)
        p.drawText(QRectF(cx - inner / 2, cy - 12, inner, 26), Qt.AlignmentFlag.AlignCenter, big)
        p.setPen(muted)
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(cx - inner / 2, cy + 12, inner, 16), Qt.AlignmentFlag.AlignCenter, small)

        # legend
        if legend_w:
            p.setFont(QFont("Segoe UI", 9))
            fm = QFontMetrics(p.font())
            row_h = 22
            y = cy - len(self.data) * row_h / 2
            for i, (name, value) in enumerate(self.data):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(SLICE_COLORS[i % len(SLICE_COLORS)]))
                p.drawRoundedRect(QRectF(lx, y + 6, 10, 10), 3, 3)
                p.setPen(QColor(pal["strong"]) if i == hover else QColor(pal["text"]))
                p.drawText(QRectF(lx + 16, y, legend_w - 64, row_h),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                           fm.elidedText(name, Qt.TextElideMode.ElideRight, legend_w - 66))
                p.setPen(muted)
                p.drawText(QRectF(lx + legend_w - 48, y, 44, row_h),
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                           f"{value / total * 100:.0f}%")
                y += row_h

    def mouseMoveEvent(self, event):
        total = sum(v for _, v in self.data)
        if total <= 0:
            return
        cx, cy, d, th, *_ = self._geometry(self.width(), self.height())
        dx, dy = event.position().x() - cx, event.position().y() - cy
        r = math.hypot(dx, dy)
        idx = -1
        if d / 2 - th - 6 <= r <= d / 2 + 4:
            angle = (90 - math.degrees(math.atan2(-dy, dx))) % 360  # clockwise from 12 o'clock
            acc = 0.0
            for i, (_, v) in enumerate(self.data):
                acc += v / total * 360
                if angle <= acc:
                    idx = i
                    break
        if idx != self.hover:
            self.hover = idx
            self.update()
        if idx >= 0:
            name, v = self.data[idx]
            QToolTip.showText(event.globalPosition().toPoint(),
                              f"<b>{html.escape(name)}</b><br>{money(v)} ({v / total * 100:.1f}%)", self)
        else:
            QToolTip.hideText()


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------
class TransactionDialog(QDialog):
    def __init__(self, parent=None, row=None, categories=None, mode="add", recurring=False):
        super().__init__(parent)
        titles = {"edit": "Edit transaction", "duplicate": "Duplicate transaction"}
        self.setWindowTitle("New recurring transaction" if recurring else titles.get(mode, "Add transaction"))
        self.setMinimumWidth(480)
        self.add_another = False
        layout = QGridLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setVerticalSpacing(14)

        layout.addWidget(QLabel("Type"), 0, 0)
        self.kind = QComboBox()
        self.kind.addItems(list(core.KINDS))
        layout.addWidget(self.kind, 0, 1)

        layout.addWidget(QLabel("Amount"), 1, 0)
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0.01, 999999999999.0)
        self.amount.setDecimals(2)
        self.amount.setGroupSeparatorShown(True)
        self.amount.setSuffix(" DZD")
        layout.addWidget(self.amount, 1, 1)

        layout.addWidget(QLabel("Category"), 2, 0)
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(categories or CATEGORIES)
        layout.addWidget(self.category, 2, 1)

        layout.addWidget(QLabel("Starts on" if recurring else "Date"), 3, 0)
        self.dt = QDateEdit(QDate.currentDate())
        self.dt.setCalendarPopup(True)
        self.dt.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.dt, 3, 1)

        next_row = 4
        self.day = None
        if recurring:
            layout.addWidget(QLabel("Repeats on day"), 4, 0)
            self.day = QSpinBox()
            self.day.setRange(1, 31)
            self.day.setValue(QDate.currentDate().day())
            self.day.setSuffix("  of every month")
            layout.addWidget(self.day, 4, 1)
            next_row = 5

        layout.addWidget(QLabel("Note"), next_row, 0)
        self.note = QLineEdit()
        self.note.setPlaceholderText("Optional note")
        layout.addWidget(self.note, next_row, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = make_button("Cancel", slot=self.reject)
        buttons.addWidget(cancel)
        if mode == "add" and not recurring:
            another = make_button("Save && add another", slot=self._save_another,
                                  tip="Save and immediately open an empty form")
            buttons.addWidget(another)
        save = make_button("Save", name="primary", slot=self.accept)
        save.setDefault(True)
        buttons.addWidget(save)
        layout.addLayout(buttons, next_row + 1, 0, 1, 2)

        if row:
            self.kind.setCurrentText(row["kind"])
            self.amount.setValue(float(row["amount"]))
            self.category.setCurrentText(row["category"] or "Other")
            if mode == "edit":
                self.dt.setDate(QDate.fromString(row["tx_date"], "yyyy-MM-dd"))
            self.note.setText(row["note"] or "")
        self.amount.setFocus()
        self.amount.selectAll()

    def _save_another(self):
        self.add_another = True
        self.accept()

    def values(self):
        category = self.category.currentText().strip() or "Other"
        return (
            self.kind.currentText(),
            self.amount.value(),
            category,
            self.dt.date().toString("yyyy-MM-dd"),
            self.note.text().strip(),
        )


class BudgetDialog(QDialog):
    def __init__(self, parent=None, budgets=None, categories=None):
        super().__init__(parent)
        self.setWindowTitle("Monthly category budgets")
        self.setMinimumWidth(520)
        self.budgets = budgets or {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.addWidget(QLabel("Set an optional monthly spending limit for each category (0 = no limit)."))

        self.inputs = {}
        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        for i, cat in enumerate(categories or CATEGORIES):
            grid.addWidget(QLabel(cat), i, 0)
            box = QDoubleSpinBox()
            box.setRange(0, 999999999999.0)
            box.setDecimals(2)
            box.setGroupSeparatorShown(True)
            box.setSuffix(" DZD")
            box.setValue(float(self.budgets.get(cat, 0)))
            self.inputs[cat] = box
            grid.addWidget(box, i, 1)
        holder = QWidget()
        holder.setLayout(grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(holder)
        scroll.setMinimumHeight(min(60 + 46 * len(self.inputs), 420))
        layout.addWidget(scroll)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(make_button("Cancel", slot=self.reject))
        save = make_button("Save", name="primary", slot=self.accept)
        save.setDefault(True)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def values(self):
        return {cat: box.value() for cat, box in self.inputs.items()}


class RecurringDialog(QDialog):
    def __init__(self, parent, categories):
        super().__init__(parent)
        self.setWindowTitle("Recurring transactions")
        self.setMinimumSize(720, 420)
        self.categories = categories
        self.changed = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        info = QLabel("Rules here create a transaction automatically every month (rent, salary, subscriptions…).\n"
                      "Missed months since the start date are filled in the next time the app opens.")
        info.setObjectName("muted")
        layout.addWidget(info)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Day", "Type", "Category", "Amount", "Note", "Starts"])
        hdr = self.table.horizontalHeader()
        for col in (0, 1, 2, 3, 5):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        buttons.addWidget(make_button("Add rule", "add", "primary", slot=self.add_rule, icon_color="#ffffff"))
        buttons.addWidget(make_button("Delete rule", "delete", "danger", slot=self.delete_rule))
        buttons.addStretch()
        buttons.addWidget(make_button("Close", slot=self.accept))
        layout.addLayout(buttons)
        self.reload()

    def reload(self):
        self.table.setRowCount(0)
        for r in core.list_recurring():
            i = self.table.rowCount()
            self.table.insertRow(i)
            income = r["kind"] == "Income"
            amount = QTableWidgetItem(("+" if income else "") + money(r["amount"]))
            amount.setForeground(QColor(T["green"] if income else T["red"]))
            amount.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            first = QTableWidgetItem(str(r["day"]))
            first.setData(Qt.ItemDataRole.UserRole, r["id"])
            first.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, first)
            self.table.setItem(i, 1, QTableWidgetItem(r["kind"]))
            self.table.setItem(i, 2, QTableWidgetItem(r["category"] or "Other"))
            self.table.setItem(i, 3, amount)
            self.table.setItem(i, 4, QTableWidgetItem(r["note"] or ""))
            self.table.setItem(i, 5, QTableWidgetItem(r["start_date"]))

    def add_rule(self):
        dlg = TransactionDialog(self, categories=self.categories, recurring=True)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        kind, amount, category, start, note = dlg.values()
        core.add_recurring(kind, amount, category, note, dlg.day.value(), start)
        self.changed = True
        self.reload()

    def delete_rule(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Recurring", "Select a rule first.")
            return
        core.delete_recurring(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        self.changed = True
        self.reload()


EXPORT_FORMATS = [
    ("Excel workbook (.xlsx)", "xlsx"),
    ("PDF report (.pdf)", "pdf"),
    ("CSV spreadsheet (.csv)", "csv"),
    ("JSON data (.json)", "json"),
]
EXPORT_INFO = {
    "xlsx": "Four sheets — Summary, Transactions, By Category and Monthly — with live formulas, filters and native charts.",
    "pdf": "A print-ready report with KPIs, charts, the category breakdown, largest expenses and every transaction.",
    "csv": "A plain table that opens in any spreadsheet and can be re-imported into this app.",
    "json": "Structured data (transactions, budgets and a summary) for scripts and other tools.",
}
EXPORT_TYPES = {
    "xlsx": ("Excel workbook (*.xlsx)", ".xlsx"),
    "pdf": ("PDF files (*.pdf)", ".pdf"),
    "csv": ("CSV files (*.csv)", ".csv"),
    "json": ("JSON files (*.json)", ".json"),
}


class ExportDialog(QDialog):
    def __init__(self, parent, counts, fmt="xlsx", scope="view"):
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setMinimumWidth(500)
        layout = QGridLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setVerticalSpacing(14)

        layout.addWidget(QLabel("What to export"), 0, 0)
        self.scope = QComboBox()
        self.scope.addItem(f"Current Transactions view  ({counts['view']})", "view")
        self.scope.addItem(f"Selected rows  ({counts['selected']})", "selected")
        self.scope.addItem(f"Everything  ({counts['all']})", "all")
        if counts["selected"] == 0:
            self.scope.model().item(1).setEnabled(False)
        self.scope.setCurrentIndex(max(self.scope.findData(scope), 0))
        layout.addWidget(self.scope, 0, 1)

        layout.addWidget(QLabel("Format"), 1, 0)
        self.fmt = QComboBox()
        for label, key in EXPORT_FORMATS:
            self.fmt.addItem(label, key)
        self.fmt.setCurrentIndex(max(self.fmt.findData(fmt), 0))
        self.fmt.currentIndexChanged.connect(self._update_info)
        layout.addWidget(self.fmt, 1, 1)

        self.info = QLabel()
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        layout.addWidget(self.info, 2, 0, 1, 2)

        self.open_after = QCheckBox("Open the file when finished")
        self.open_after.setChecked(True)
        layout.addWidget(self.open_after, 3, 0, 1, 2)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(make_button("Cancel", slot=self.reject))
        go = make_button("Export…", "export", "primary", slot=self.accept, icon_color="#ffffff")
        go.setDefault(True)
        buttons.addWidget(go)
        layout.addLayout(buttons, 4, 0, 1, 2)
        self._update_info()

    def _update_info(self):
        self.info.setText(EXPORT_INFO[self.fmt.currentData()])

    def result_values(self):
        return self.scope.currentData(), self.fmt.currentData(), self.open_after.isChecked()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    PERIODS = ["All time", "This month", "Last 30 days", "This year", "Custom range"]
    DASH_PERIODS = ["This month", "Last 30 days", "This year", "All time"]

    def __init__(self):
        super().__init__()
        self.settings = QSettings("PersonalFinanceLite", "Pro")
        self.theme = self.settings.value("theme", "dark")
        set_theme(self.theme)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(resource_path("assets/app.ico")))
        self.setWindowFilePath(str(core.DB))
        self.resize(1240, 820)
        self.setMinimumSize(980, 640)
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        self.setAcceptDrops(True)
        self.visible_rows = []
        self.undo_stack = []
        self.budgets = core.load_budgets()
        self.toast = Toast(self)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(200)
        self.search_timer.timeout.connect(self.refresh_transactions)
        self.build()
        self.setup_shortcuts()
        self.refresh_all()
        QTimer.singleShot(500, self.run_recurring)

    # ------------------------------------------------------------------ UI
    def build(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(24, 22, 24, 14)
        outer.setSpacing(14)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(2)
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        subtitle = QLabel("Offline money tracking • Private SQLite storage")
        subtitle.setObjectName("muted")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()

        add_btn = make_button("Add transaction", "add", "primary", "Add a transaction (Ctrl+N)",
                              self.open_add_dialog, icon_color="#ffffff")
        budget_btn = make_button("Budgets", "settings", tip="Manage monthly budgets", slot=self.edit_budgets)

        export_btn = make_button("Export", "export", tip="Export to Excel, PDF, CSV or JSON (Ctrl+E)")
        menu = QMenu(export_btn)
        menu.addAction("Export…\tCtrl+E", self.open_export_dialog)
        menu.addSeparator()
        menu.addAction("Excel workbook — current view", lambda: self.run_export("xlsx", "view"))
        menu.addAction("PDF report — current view", lambda: self.run_export("pdf", "view"))
        menu.addAction("CSV — current view", lambda: self.run_export("csv", "view"))
        menu.addAction("JSON — current view", lambda: self.run_export("json", "view"))
        menu.addSeparator()
        menu.addAction("Copy current view to clipboard", self.copy_view_to_clipboard)
        export_btn.setMenu(menu)

        data_btn = make_button("Data", "transactions", tip="Import, recurring rules and backups")
        dmenu = QMenu(data_btn)
        dmenu.addAction("Import CSV…", self.import_csv)
        dmenu.addAction("Recurring transactions…", self.open_recurring)
        dmenu.addSeparator()
        dmenu.addAction("Back up now", self.backup_now)
        dmenu.addAction("Restore backup…", self.restore_backup)
        dmenu.addAction("Open backup folder", self.open_backup_folder)
        data_btn.setMenu(dmenu)

        theme_btn = make_button("☀  Light" if self.theme == "dark" else "☾  Dark",
                                tip="Switch theme (Ctrl+Shift+T)", slot=self.toggle_theme)
        theme_btn.setObjectName("ghost")

        for b in (add_btn, budget_btn, export_btn, data_btn, theme_btn):
            header.addWidget(b)
        outer.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(18, 18))
        self.tabs.setDocumentMode(True)
        outer.addWidget(self.tabs, 1)
        self.build_dashboard_tab()
        self.build_transactions_tab()
        self.build_budget_tab()
        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.setStatusBar(QStatusBar())

    @staticmethod
    def panel():
        frame = QFrame()
        frame.setObjectName("panel")
        return frame

    def build_dashboard_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        tab = QWidget()
        scroll.setWidget(tab)
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(4, 12, 10, 8)
        lay.setSpacing(14)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.income_card = StatCard("Income", "green")
        self.expense_card = StatCard("Expenses", "red", good_when_up=False)
        self.balance_card = StatCard("Balance", "blue")
        self.rate_card = StatCard("Saving rate", "purple", fmt=lambda v: f"{v:.1f}%")
        for card in (self.income_card, self.expense_card, self.balance_card, self.rate_card):
            cards.addWidget(card)
        lay.addLayout(cards)

        period = self.panel()
        p = QHBoxLayout(period)
        p.setContentsMargins(16, 10, 16, 10)
        p.addWidget(QLabel("Dashboard period"))
        self.dashboard_period = QComboBox()
        self.dashboard_period.addItems(self.DASH_PERIODS)
        self.dashboard_period.setCurrentText(self.settings.value("dash_period", "This month"))
        self.dashboard_period.currentIndexChanged.connect(self.on_dashboard_period)
        p.addWidget(self.dashboard_period)
        self.compare_label = QLabel("")
        self.compare_label.setObjectName("muted")
        p.addWidget(self.compare_label)
        p.addStretch()
        hint = QLabel("Hover the charts for details • right-click to save them as images")
        hint.setObjectName("muted")
        p.addWidget(hint)
        lay.addWidget(period)

        charts = QHBoxLayout()
        charts.setSpacing(14)
        chart_panel = self.panel()
        cl = QVBoxLayout(chart_panel)
        cl.setContentsMargins(18, 16, 18, 12)
        cl.addWidget(self.section_label("Last 6 months"))
        self.chart = MonthlyChart()
        cl.addWidget(self.chart)
        charts.addWidget(chart_panel, 3)

        donut_panel = self.panel()
        dl = QVBoxLayout(donut_panel)
        dl.setContentsMargins(18, 16, 18, 12)
        dl.addWidget(self.section_label("Spending split"))
        self.donut = DonutChart()
        dl.addWidget(self.donut)
        charts.addWidget(donut_panel, 2)
        lay.addLayout(charts)

        lower = QHBoxLayout()
        lower.setSpacing(14)
        summary = self.panel()
        sl = QVBoxLayout(summary)
        sl.setContentsMargins(18, 16, 18, 16)
        sl.addWidget(self.section_label("Spending by category"))
        self.category_table = QTableWidget(0, 3)
        self.category_table.setHorizontalHeaderLabels(["Category", "Spent", "Budget progress"])
        hdr = self.category_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.category_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.category_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.category_table.verticalHeader().setVisible(False)
        self.category_table.setMinimumHeight(230)
        sl.addWidget(self.category_table)
        lower.addWidget(summary, 3)

        insights = self.panel()
        il = QVBoxLayout(insights)
        il.setContentsMargins(18, 16, 18, 16)
        il.addWidget(self.section_label("Financial snapshot"))
        self.snapshot = QLabel()
        self.snapshot.setWordWrap(True)
        self.snapshot.setObjectName("snapshot")
        self.snapshot.setTextFormat(Qt.TextFormat.RichText)
        self.snapshot.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        il.addWidget(self.snapshot)
        il.addStretch()
        lower.addWidget(insights, 2)
        lay.addLayout(lower)
        self.tabs.addTab(scroll, app_icon("dashboard"), "Dashboard")

    def build_transactions_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(4, 12, 4, 4)

        filters = self.panel()
        fl = QGridLayout(filters)
        fl.setContentsMargins(16, 14, 16, 14)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search notes or categories…   (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(QAction(app_icon("search"), "", self.search), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(lambda _t: self.search_timer.start())
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All types", "Expense", "Income"])
        self.type_filter.currentIndexChanged.connect(self.refresh_transactions)
        self.cat_filter = QComboBox()
        self.cat_filter.currentIndexChanged.connect(self.refresh_transactions)
        self.period_filter = QComboBox()
        self.period_filter.addItems(self.PERIODS)
        self.period_filter.currentIndexChanged.connect(self.on_period_changed)

        today = QDate.currentDate()
        self.from_date = QDateEdit(QDate(today.year(), today.month(), 1))
        self.to_date = QDateEdit(today)
        for edit in (self.from_date, self.to_date):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
            edit.dateChanged.connect(self.refresh_transactions)
        self.from_label = QLabel("From")
        self.to_label = QLabel("To")
        self.custom_widgets = (self.from_label, self.from_date, self.to_label, self.to_date)
        reset = make_button("Reset", tip="Clear all filters", slot=self.reset_filters)

        fl.addWidget(QLabel("Search"), 0, 0)
        fl.addWidget(self.search, 0, 1, 1, 2)
        fl.addWidget(QLabel("Type"), 0, 3)
        fl.addWidget(self.type_filter, 0, 4)
        fl.addWidget(QLabel("Category"), 0, 5)
        fl.addWidget(self.cat_filter, 0, 6)
        fl.addWidget(QLabel("Period"), 0, 7)
        fl.addWidget(self.period_filter, 0, 8)
        fl.addWidget(reset, 0, 9)
        fl.addWidget(self.from_label, 1, 3)
        fl.addWidget(self.from_date, 1, 4)
        fl.addWidget(self.to_label, 1, 5)
        fl.addWidget(self.to_date, 1, 6)
        for w in self.custom_widgets:
            w.setVisible(False)
        lay.addWidget(filters)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Type", "Category", "Amount", "Note", "ID"])
        self.table.setColumnHidden(5, True)
        hdr = self.table.horizontalHeader()
        for col in range(4):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hdr.setSortIndicator(0, Qt.SortOrder.DescendingOrder)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.doubleClicked.connect(lambda _i: self.edit_selected())
        self.table.itemSelectionChanged.connect(self.update_selection_summary)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.table_menu)
        for seq, slot in (("Delete", self.delete_selected), ("Ctrl+C", self.copy_selected),
                          ("Return", self.edit_selected), ("Enter", self.edit_selected)):
            sc = QShortcut(QKeySequence(seq), self.table, activated=slot)
            sc.setContext(Qt.ShortcutContext.WidgetShortcut)
        lay.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        add = make_button("Add", "add", "primary", slot=self.open_add_dialog, icon_color="#ffffff")
        edit = make_button("Edit", "edit", slot=self.edit_selected)
        dup = make_button("Duplicate", "add", tip="Copy the selected transaction with today's date",
                          slot=self.duplicate_selected)
        delete = make_button("Delete", "delete", "danger", "Delete the selected transactions (Del) — Ctrl+Z undoes it",
                             self.delete_selected)
        clear = make_button("Clear all", "clear", slot=self.clear_all)
        for b in (add, edit, dup, delete, clear):
            buttons.addWidget(b)
        buttons.addStretch()
        self.selection_label = QLabel("")
        self.selection_label.setObjectName("accentText")
        buttons.addWidget(self.selection_label)
        self.result_count = QLabel("0 transactions")
        self.result_count.setObjectName("muted")
        buttons.addWidget(self.result_count)
        lay.addLayout(buttons)
        self.tabs.addTab(tab, app_icon("transactions"), "Transactions")

    def build_budget_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(4, 12, 4, 4)
        head = QHBoxLayout()
        head.addWidget(self.section_label("Monthly budget control"))
        head.addStretch()
        head.addWidget(make_button("Edit budgets", "settings", slot=self.edit_budgets))
        lay.addLayout(head)
        self.budget_table = QTableWidget(0, 5)
        self.budget_table.setHorizontalHeaderLabels(["Category", "Budget", "Spent this month", "Remaining", "Progress"])
        self.budget_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.budget_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.budget_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.budget_table.verticalHeader().setVisible(False)
        self.budget_table.verticalHeader().setDefaultSectionSize(38)
        lay.addWidget(self.budget_table, 1)
        self.tabs.addTab(tab, app_icon("budget"), "Budgets")

    def setup_shortcuts(self):
        for seq, slot in (
            ("Ctrl+N", self.open_add_dialog), ("Ctrl+F", self.focus_search), ("F5", self.refresh_all),
            ("Ctrl+E", self.open_export_dialog), ("Ctrl+Z", self.undo), ("Ctrl+Shift+T", self.toggle_theme),
            ("Ctrl+1", lambda: self.tabs.setCurrentIndex(0)), ("Ctrl+2", lambda: self.tabs.setCurrentIndex(1)),
            ("Ctrl+3", lambda: self.tabs.setCurrentIndex(2)),
        ):
            QShortcut(QKeySequence(seq), self, activated=slot)

    def focus_search(self):
        self.tabs.setCurrentIndex(1)
        self.search.setFocus()
        self.search.selectAll()

    @staticmethod
    def section_label(text):
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    # ------------------------------------------------------ polish & theme
    def on_tab_changed(self, index):
        page = self.tabs.widget(index)
        if page is None:
            return
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", page)
        anim.setDuration(240)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: page.setGraphicsEffect(None))
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        if index == 0:
            self.chart.play()
            self.donut.play()

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.settings.setValue("theme", self.theme)
        set_theme(self.theme)
        apply_style(QApplication.instance())
        tab = self.tabs.currentIndex()
        self.settings.setValue("dash_period", self.dashboard_period.currentText())
        self.build()
        self.refresh_all(animate=False)
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(tab)
        self.tabs.blockSignals(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.toast.isVisible():
            self.toast.reposition()

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("dash_period", self.dashboard_period.currentText())
        super().closeEvent(event)

    # ------------------------------------------------------- drag & drop
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith(".csv") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".csv"):
                self.import_csv_path(path)
                break

    # ------------------------------------------------------------ helpers
    def all_categories(self):
        return CATEGORIES + core.extra_categories()

    def sync_category_filter(self):
        current = self.cat_filter.currentText() or "All categories"
        self.cat_filter.blockSignals(True)
        self.cat_filter.clear()
        self.cat_filter.addItem("All categories")
        self.cat_filter.addItems(self.all_categories())
        index = self.cat_filter.findText(current)
        self.cat_filter.setCurrentIndex(max(index, 0))
        self.cat_filter.blockSignals(False)

    def on_period_changed(self):
        custom = self.period_filter.currentText() == "Custom range"
        for w in self.custom_widgets:
            w.setVisible(custom)
        self.refresh_transactions()

    def reset_filters(self):
        for w in (self.search, self.type_filter, self.cat_filter, self.period_filter):
            w.blockSignals(True)
        self.search.clear()
        self.type_filter.setCurrentIndex(0)
        self.cat_filter.setCurrentIndex(0)
        self.period_filter.setCurrentIndex(0)
        for w in (self.search, self.type_filter, self.cat_filter, self.period_filter):
            w.blockSignals(False)
        for w in self.custom_widgets:
            w.setVisible(False)
        self.refresh_transactions()

    def tx_range(self):
        period = self.period_filter.currentText()
        if period == "Custom range":
            start = self.from_date.date().toString("yyyy-MM-dd")
            end = self.to_date.date().toString("yyyy-MM-dd")
            return (min(start, end), max(start, end))
        return core.get_range(period)

    def filters_text(self):
        start, end = self.tx_range()
        parts = [f"{start} to {end}" if start else "all dates"]
        if self.type_filter.currentIndex() > 0:
            parts.append(self.type_filter.currentText())
        if self.cat_filter.currentIndex() > 0:
            parts.append(self.cat_filter.currentText())
        if self.search.text().strip():
            parts.append(f"search \"{self.search.text().strip()}\"")
        return ", ".join(parts)

    def selected_ids(self):
        ids = []
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), 5)
            if item:
                ids.append(int(item.text()))
        return ids

    def single_selected_id(self, title):
        ids = self.selected_ids()
        if not ids:
            self.toast.show_message("Select a transaction first", kind="warn", ms=2500)
            return None
        if len(ids) > 1:
            self.toast.show_message("Select only one transaction", kind="warn", ms=2500)
            return None
        return ids[0]

    def reload_after_data_change(self):
        self.budgets = core.load_budgets()
        self.refresh_all()

    def update_selection_summary(self):
        ids = set(self.selected_ids())
        if not ids:
            self.selection_label.setText("")
            return
        chosen = [r for r in self.visible_rows if r["id"] in ids]
        income, expense = core.totals(chosen)
        self.selection_label.setText(
            f"{len(chosen)} selected  •  +{money(income)}  /  −{money(expense)}  •  Net {money(income - expense)}"
        )

    # -------------------------------------------------------------- undo
    def push_undo(self, label, fn):
        self.undo_stack.append((label, fn))
        del self.undo_stack[:-30]

    def undo(self):
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit) and focus.isUndoAvailable():
            focus.undo()  # typing in a text box: Ctrl+Z undoes the text, not the last transaction
            return
        if not self.undo_stack:
            self.toast.show_message("Nothing to undo", ms=2000)
            return
        label, fn = self.undo_stack.pop()
        try:
            fn()
        except Exception as exc:
            QMessageBox.critical(self, "Undo failed", str(exc))
            return
        self.refresh_all()
        self.toast.show_message(f"Undone: {label}", ms=2500)

    def notify(self, text, kind="ok", with_undo=True):
        if with_undo and self.undo_stack:
            self.toast.show_message(text, "Undo", self.undo, kind=kind)
        else:
            self.toast.show_message(text, kind=kind)

    # ------------------------------------------------------------ budgets
    def edit_budgets(self):
        dialog = BudgetDialog(self, self.budgets, self.all_categories())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        core.save_budgets(dialog.values())
        self.reload_after_data_change()
        self.toast.show_message("Budgets updated", kind="ok", ms=3000)

    def budget_warning(self, values):
        kind, _amount, category, tx_date, _note = values
        if kind != "Expense" or tx_date[:7] != f"{date.today():%Y-%m}":
            return ""
        budget = float(self.budgets.get(category, 0))
        if budget <= 0:
            return ""
        start, end = core.month_bounds(date.today().year, date.today().month)
        spent = core.category_spending(core.fetch_transactions(start, end)).get(category, 0.0)
        pct = spent / budget * 100
        if pct > 100:
            return f"  ⚠ {category} is over budget ({pct:.0f}%)"
        if pct >= 80:
            return f"  ⚠ {category} budget at {pct:.0f}%"
        return ""

    # ----------------------------------------------------------- refreshing
    def refresh_all(self, animate=True):
        self.budgets = core.load_budgets()
        self.sync_category_filter()
        self.refresh_dashboard(animate)
        self.refresh_transactions()
        self.refresh_budgets()
        self.update_backup_status()

    def update_backup_status(self):
        last = core.latest_backup()
        text = f"Database: {core.DB}"
        if last is not None:
            when = datetime.fromtimestamp(last.stat().st_mtime)
            text += f"   •   Last backup: {when:%Y-%m-%d %H:%M}"
        text += "   •   Ctrl+Z undo  •  Ctrl+E export"
        self.statusBar().showMessage(text)

    def on_dashboard_period(self):
        self.settings.setValue("dash_period", self.dashboard_period.currentText())
        self.refresh_dashboard()

    def refresh_dashboard(self, animate=True):
        period = self.dashboard_period.currentText()
        start, end = core.get_range(period)
        rows = core.fetch_transactions(start, end)
        income, expense = core.totals(rows)
        balance = income - expense
        rate = (balance / income * 100) if income else 0

        pstart, pend = core.previous_range(period)
        d_inc = d_exp = d_bal = None
        if pstart:
            p_inc, p_exp = core.totals(core.fetch_transactions(pstart, pend))
            d_inc, d_exp = core.pct_change(income, p_inc), core.pct_change(expense, p_exp)
            d_bal = core.pct_change(balance, p_inc - p_exp)
            self.compare_label.setText(f"  compared with {pstart} → {pend}")
        else:
            self.compare_label.setText("  (no comparison for all-time)")
        self.income_card.set_value(income, d_inc, animate)
        self.expense_card.set_value(expense, d_exp, animate)
        self.balance_card.set_value(balance, d_bal, animate)
        self.rate_card.set_value(rate, None, animate)

        ordered = sorted(core.category_spending(rows).items(), key=lambda x: x[1], reverse=True)
        self.category_table.setRowCount(0)
        for cat, spent in ordered:
            i = self.category_table.rowCount()
            self.category_table.insertRow(i)
            self.category_table.setItem(i, 0, QTableWidgetItem(cat))
            amount_item = QTableWidgetItem(money(spent))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.category_table.setItem(i, 1, amount_item)
            self.category_table.setCellWidget(i, 2, make_bar(spent, float(self.budgets.get(cat, 0))))

        self.chart.set_data(core.month_series(6), animate)
        self.donut.set_data(ordered, animate)

        esc = html.escape
        muted, strong = T["muted"], T["strong"]

        def kv(label, value):
            return (f"<p style='margin:0 0 9px 0;'><span style='color:{muted};font-size:11px;'>{label}</span>"
                    f"<br><b style='color:{strong};'>{value}</b></p>")

        top = ordered[0] if ordered else None
        biggest = core.top_expenses(rows, 1)
        spent_so_far, projected = core.month_projection()
        total_budget = sum(v for v in self.budgets.values() if v > 0)
        proj_color = T["red"] if total_budget and projected > total_budget else strong
        over = core.over_budget(self.budgets)
        over_text = ", ".join(esc(c) for c, _, _ in over) if over else "None"
        html_parts = [
            kv("Transactions in period", str(len(rows))),
            kv("Largest expense category",
               f"{esc(top[0])} — {money(top[1])} ({top[1] / expense * 100:.0f}%)" if top else "—"),
            kv("Average daily spending", money(core.daily_average_spend(rows, start, end))),
            kv("Projected spending this month",
               f"<span style='color:{proj_color};'>{money(projected)}</span>"),
            kv("Biggest single expense",
               (f"{money(float(biggest[0]['amount']))} • {esc(biggest[0]['category'] or 'Other')}" if biggest else "—")),
            kv("Over budget this month",
               f"<span style='color:{T['red'] if over else T['green']};'>{over_text}</span>"),
        ]
        self.snapshot.setText("".join(html_parts))

    def refresh_transactions(self):
        start, end = self.tx_range()
        rows = core.fetch_transactions(start, end)
        type_filter = self.type_filter.currentText()
        cat_filter = self.cat_filter.currentText()
        query = self.search.text().strip().lower()
        filtered = []
        for r in rows:
            if type_filter != "All types" and r["kind"] != type_filter:
                continue
            if cat_filter != "All categories" and (r["category"] or "Other") != cat_filter:
                continue
            haystack = f"{r['category'] or ''} {r['note'] or ''}".lower()
            if query and query not in haystack:
                continue
            filtered.append(r)
        self.visible_rows = filtered

        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))
        for i, r in enumerate(filtered):
            income = r["kind"] == "Income"
            amount_item = NumericItem(("+" if income else "") + money(r["amount"]))
            amount_item.setData(Qt.ItemDataRole.UserRole, float(r["amount"]))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            amount_item.setForeground(QColor(T["green"] if income else T["red"]))
            type_item = QTableWidgetItem(r["kind"])
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_item.setForeground(QColor(T["green"] if income else T["red"]))
            self.table.setItem(i, 0, QTableWidgetItem(r["tx_date"]))
            self.table.setItem(i, 1, type_item)
            self.table.setItem(i, 2, QTableWidgetItem(r["category"] or "Other"))
            self.table.setItem(i, 3, amount_item)
            self.table.setItem(i, 4, QTableWidgetItem(r["note"] or ""))
            self.table.setItem(i, 5, QTableWidgetItem(str(r["id"])))
        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)

        income, expense = core.totals(filtered)
        count = len(filtered)
        self.result_count.setText(
            f"{count} transaction{'s' if count != 1 else ''}  •  "
            f"Income {money(income)}  •  Expenses {money(expense)}  •  Net {money(income - expense)}"
        )
        self.update_selection_summary()

    def refresh_budgets(self):
        today = date.today()
        start, end = core.month_bounds(today.year, today.month)
        spent = core.category_spending(core.fetch_transactions(start, end))
        self.budget_table.setRowCount(0)
        for cat in self.all_categories():
            budget = float(self.budgets.get(cat, 0))
            current = spent.get(cat, 0)
            if budget <= 0 and current <= 0:
                continue
            remaining = budget - current if budget > 0 else 0
            i = self.budget_table.rowCount()
            self.budget_table.insertRow(i)
            vals = [cat, money(budget) if budget > 0 else "Not set", money(current),
                    money(remaining) if budget > 0 else "—"]
            for j, value in enumerate(vals):
                item = QTableWidgetItem(value)
                if j > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if j == 3 and budget > 0:
                    item.setForeground(QColor(T["red"] if remaining < 0 else T["green"]))
                self.budget_table.setItem(i, j, item)
            self.budget_table.setCellWidget(i, 4, make_bar(current, budget))

    # --------------------------------------------------------- transactions
    def open_add_dialog(self):
        while True:
            dialog = TransactionDialog(self, categories=self.all_categories())
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            values = dialog.values()
            new_id = core.add_transaction(values)
            self.push_undo("add transaction", lambda i=new_id: core.delete_transactions([i]))
            self.refresh_all()
            warning = self.budget_warning(values)
            self.notify("Transaction added" + warning, kind="warn" if warning else "ok")
            if not dialog.add_another:
                return

    def edit_selected(self):
        ident = self.single_selected_id("Edit transaction")
        if ident is None:
            return
        row = core.get_transaction(ident)
        if not row:
            return
        old = (row["kind"], row["amount"], row["category"], row["tx_date"], row["note"])
        dialog = TransactionDialog(self, row, self.all_categories(), mode="edit")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        core.update_transaction(ident, values)
        self.push_undo("edit transaction", lambda: core.update_transaction(ident, old))
        self.refresh_all()
        warning = self.budget_warning(values)
        self.notify("Transaction updated" + warning, kind="warn" if warning else "ok")

    def duplicate_selected(self):
        ident = self.single_selected_id("Duplicate transaction")
        if ident is None:
            return
        row = core.get_transaction(ident)
        if not row:
            return
        dialog = TransactionDialog(self, row, self.all_categories(), mode="duplicate")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        new_id = core.add_transaction(values)
        self.push_undo("duplicate transaction", lambda: core.delete_transactions([new_id]))
        self.refresh_all()
        self.notify("Transaction duplicated")

    def delete_selected(self):
        ids = self.selected_ids()
        if not ids:
            self.toast.show_message("Select a transaction first", kind="warn", ms=2500)
            return
        noun = "transaction" if len(ids) == 1 else f"{len(ids)} transactions"
        if len(ids) > 10:
            answer = QMessageBox.question(self, "Delete transactions", f"Delete {noun}? You can undo this with Ctrl+Z.",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        rows = [dict(r) for r in (core.get_transaction(i) for i in ids) if r]
        core.delete_transactions(ids)
        self.push_undo(f"delete {noun}", lambda: core.restore_transactions(rows))
        self.refresh_all()
        self.notify(f"Deleted {noun}", kind="info")

    def clear_all(self):
        answer = QMessageBox.warning(
            self, "Clear all data",
            "This will delete every transaction.\nA backup is created first, and you can undo with Ctrl+Z. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            core.make_backup("before-clear")
        except Exception as exc:  # never delete data if the safety copy failed
            QMessageBox.critical(self, "Backup failed", f"Nothing was deleted.\n\n{exc}")
            return
        rows = [dict(r) for r in core.fetch_transactions()]
        core.clear_transactions()
        self.push_undo("clear all", lambda: core.restore_transactions(rows))
        self.refresh_all()
        self.notify("All transactions cleared (backup saved)", kind="info")

    def table_menu(self, pos):
        index = self.table.indexAt(pos)
        if index.isValid() and not self.table.selectionModel().isRowSelected(index.row(), index.parent()):
            self.table.selectRow(index.row())
        ids = self.selected_ids()
        menu = QMenu(self)
        edit = menu.addAction(app_icon("edit"), "Edit", self.edit_selected)
        dup = menu.addAction(app_icon("add"), "Duplicate", self.duplicate_selected)
        edit.setEnabled(len(ids) == 1)
        dup.setEnabled(len(ids) == 1)
        menu.addSeparator()
        cp = menu.addAction("Copy rows\tCtrl+C", self.copy_selected)
        cp.setEnabled(bool(ids))
        ex = menu.addAction(app_icon("export"), "Export selected…", lambda: self.open_export_dialog(scope="selected"))
        ex.setEnabled(bool(ids))
        menu.addSeparator()
        rm = menu.addAction(app_icon("delete"), "Delete\tDel", self.delete_selected)
        rm.setEnabled(bool(ids))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------ clipboard
    @staticmethod
    def rows_to_tsv(rows):
        lines = ["Date\tType\tCategory\tAmount\tNote"]
        for r in rows:
            note = (r["note"] or "").replace("\t", " ").replace("\n", " ")
            lines.append(f"{r['tx_date']}\t{r['kind']}\t{r['category'] or 'Other'}\t{float(r['amount']):.2f}\t{note}")
        return "\n".join(lines)

    def copy_selected(self):
        ids = set(self.selected_ids())
        rows = [r for r in self.visible_rows if r["id"] in ids]
        if not rows:
            return
        QApplication.clipboard().setText(self.rows_to_tsv(rows))
        self.toast.show_message(f"Copied {len(rows)} row{'s' if len(rows) != 1 else ''} — paste into Excel or Sheets",
                                kind="ok", ms=3000)

    def copy_view_to_clipboard(self):
        if not self.visible_rows:
            self.toast.show_message("There is nothing to copy in the current view", kind="warn", ms=3000)
            return
        QApplication.clipboard().setText(self.rows_to_tsv(self.visible_rows))
        self.toast.show_message(f"Copied {len(self.visible_rows)} rows — paste into Excel or Sheets", kind="ok", ms=3000)

    # ------------------------------------------------------------ recurring
    def run_recurring(self):
        try:
            created = core.apply_recurring()
        except Exception as exc:
            self.toast.show_message(f"Recurring transactions failed: {exc}", kind="warn")
            return
        if created:
            self.refresh_all()
            self.toast.show_message(f"{created} recurring transaction{'s' if created != 1 else ''} added", kind="ok")

    def open_recurring(self):
        dialog = RecurringDialog(self, self.all_categories())
        dialog.exec()
        if dialog.changed:
            self.run_recurring()
            self.refresh_all()

    # ------------------------------------------------------ import / export
    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import transactions", str(Path.home()), "CSV files (*.csv)")
        if path:
            self.import_csv_path(path)

    def import_csv_path(self, path):
        try:
            core.make_backup("before-import")
            added, duplicates, invalid = core.import_csv(path)
        except (OSError, UnicodeDecodeError) as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        self.refresh_all()
        self.toast.show_message(
            f"Imported {added} • skipped {duplicates} duplicates • {invalid} invalid rows",
            kind="ok" if added else "warn", ms=7000,
        )

    def rows_for_scope(self, scope):
        if scope == "selected":
            ids = set(self.selected_ids())
            return [r for r in self.visible_rows if r["id"] in ids]
        if scope == "all":
            return core.fetch_transactions()
        return list(self.visible_rows)

    def open_export_dialog(self, fmt="xlsx", scope=None):
        if not isinstance(fmt, str):  # triggered from a QAction/shortcut with a bool argument
            fmt = "xlsx"
        counts = {"view": len(self.visible_rows), "selected": len(self.selected_ids()), "all": core.count_transactions()}
        scope = scope or ("selected" if counts["selected"] else "view")
        dialog = ExportDialog(self, counts, fmt, scope)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        chosen_scope, chosen_fmt, open_after = dialog.result_values()
        self.run_export(chosen_fmt, chosen_scope, open_after)

    def run_export(self, fmt, scope, open_after=True):
        rows = self.rows_for_scope(scope)
        if not rows:
            QMessageBox.information(
                self, "Export",
                "There are no transactions to export for this choice.\n"
                "Adjust the filters on the Transactions tab, or choose “Everything”."
            )
            return
        label, ext = EXPORT_TYPES[fmt]
        folder = Path(self.settings.value("export_dir", str(Path.home())))
        default = folder / f"personal-finance-{date.today():%Y-%m-%d}{ext}"
        path, _ = QFileDialog.getSaveFileName(self, "Export", str(default), label)
        if not path:
            return
        if not path.lower().endswith(ext):
            path += ext
        filters_text = {"view": self.filters_text(), "selected": "selected rows", "all": "all transactions"}[scope]

        error = None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if fmt == "xlsx":
                core.export_xlsx(path, rows, self.budgets, filters_text)
            elif fmt == "pdf":
                self.write_pdf(path, rows, filters_text)
            elif fmt == "csv":
                core.export_csv(path, rows)
            else:
                core.export_json(path, rows, self.budgets, filters_text)
        except PermissionError:
            error = "The file could not be written. If it is open in Excel or another program, close it and try again."
        except ImportError as exc:
            error = f"A required component is missing: {exc}\nRun:  pip install -r requirements.txt"
        except Exception as exc:
            error = str(exc)
        finally:
            QApplication.restoreOverrideCursor()
        if error:
            QMessageBox.critical(self, "Export failed", error)
            return

        self.settings.setValue("export_dir", str(Path(path).parent))
        url = QUrl.fromLocalFile(path)
        self.toast.show_message(
            f"Exported {len(rows)} transaction{'s' if len(rows) != 1 else ''} → {Path(path).name}",
            "Open", lambda: QDesktopServices.openUrl(url), kind="ok", ms=8000,
        )
        if open_after:
            QDesktopServices.openUrl(url)

    def write_pdf(self, path, rows, filters_text):
        light = LIGHT
        months = core.monthly_totals(rows)[-12:]
        bars = MonthlyChart()
        bars.data = [(datetime.strptime(k, "%Y-%m").strftime("%b"), inc, exp) for k, inc, exp in months]
        donut = DonutChart()
        donut.set_data(sorted(core.category_spending(rows).items(), key=lambda x: x[1], reverse=True), animate=False)

        doc = QTextDocument()
        doc.setDefaultFont(QFont("Segoe UI", 9))
        names = [None, None]
        if any(inc or exp for _, inc, exp in months):
            doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("bar.png"), bars.to_image(440, 190, light))
            names[0] = "bar.png"
        if donut.data:
            doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("donut.png"), donut.to_image(300, 190, light))
            names[1] = "donut.png"
        doc.setHtml(core.build_report_html(rows, filters_text, names[0], names[1]))

        writer = QPdfWriter(path)
        writer.setResolution(96)  # 1 CSS-style pixel == 1 device unit, so image sizes match the layout
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
        writer.setTitle(f"{APP_NAME} report")
        writer.setCreator(APP_NAME)
        doc.print_(writer)

    # -------------------------------------------------------------- backups
    def backup_now(self):
        try:
            dest = core.make_backup("manual")
        except Exception as exc:
            QMessageBox.critical(self, "Backup failed", str(exc))
            return
        if dest is None:
            self.toast.show_message("There is no data to back up yet", kind="warn", ms=3000)
            return
        self.update_backup_status()
        self.toast.show_message(f"Backup saved: {dest.name}", "Open folder", self.open_backup_folder, kind="ok")

    def restore_backup(self):
        core.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(
            self, "Restore backup", str(core.BACKUP_DIR), "Database backups (*.db)"
        )
        if not path:
            return
        answer = QMessageBox.warning(
            self, "Restore backup",
            "This replaces your current data with the selected backup.\n"
            "Your current data is backed up first. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            core.restore_backup(path)
        except Exception as exc:
            QMessageBox.critical(self, "Restore failed", str(exc))
            return
        self.undo_stack.clear()
        self.reload_after_data_change()
        self.toast.show_message("Backup restored", kind="ok")

    def open_backup_folder(self):
        core.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(core.BACKUP_DIR)))


STYLE = """
QWidget { background: @bg; color: @text; }
QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget { background: @bg; }
QLabel { background: transparent; }
QLabel#appTitle { font-size: 28px; font-weight: 800; color: @strong; }
QLabel#muted, QLabel#statTitle { color: @muted; }
QLabel#accentText { color: @blue; font-weight: 600; }
QLabel#sectionTitle { font-size: 16px; font-weight: 700; color: @strong; }
QLabel#snapshot { color: @text; }
QFrame#panel { background: @panel; border: 1px solid @border; border-radius: 16px; }
QFrame#panel QLabel, QFrame#statCard QLabel { background: transparent; }
QFrame#statCard { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 @card_a, stop:1 @card_b); border: 1px solid @border; border-radius: 17px; }
QFrame#statCard[accent="green"] { border-left: 4px solid @green; }
QFrame#statCard[accent="red"] { border-left: 4px solid @red; }
QFrame#statCard[accent="blue"] { border-left: 4px solid @blue; }
QFrame#statCard[accent="purple"] { border-left: 4px solid @purple; }
QLabel#statValue { font-size: 21px; font-weight: 800; color: @strong; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QDateEdit {
    background: @input; border: 1px solid @border2; border-radius: 9px; padding: 8px 11px; min-height: 20px; selection-background-color: @select;
}
QLineEdit:hover, QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover, QDateEdit:hover { border: 1px solid @muted; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QDateEdit:focus { border: 1px solid @blue; }
QComboBox QAbstractItemView { background: @panel; color: @text; selection-background-color: @select; selection-color: @strong; border: 1px solid @border2; outline: 0; }
QCheckBox { spacing: 8px; background: transparent; }
QPushButton { background: @btn; border: 1px solid @btnborder; border-radius: 9px; padding: 8px 15px; font-weight: 600; color: @text; }
QPushButton:hover { background: @hover; }
QPushButton:pressed { background: @select; }
QPushButton:disabled { color: @muted; }
QPushButton::menu-indicator { subcontrol-position: right center; right: 6px; }
QPushButton#primary { background: @accent; border-color: @accent; color: white; }
QPushButton#primary:hover { background: @accent_h; border-color: @accent_h; }
QPushButton#danger { background: @danger_bg; border-color: @danger_bd; color: @danger_tx; }
QPushButton#danger:hover { background: @danger_h; }
QPushButton#ghost { background: transparent; border: 1px solid transparent; color: @muted; }
QPushButton#ghost:hover { background: @hover; color: @strong; }
QMenu { background: @panel; color: @text; border: 1px solid @border; padding: 6px; border-radius: 10px; }
QMenu::item { padding: 8px 26px 8px 18px; border-radius: 6px; }
QMenu::item:selected { background: @select; color: @strong; }
QMenu::item:disabled { color: @muted; }
QMenu::separator { height: 1px; background: @border; margin: 6px 4px; }
QTabWidget::pane { border: 0; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: @muted; padding: 10px 18px; margin-right: 4px; border-radius: 9px; font-weight: 600; }
QTabBar::tab:hover { color: @strong; background: @hover; }
QTabBar::tab:selected { background: @tab_sel; color: @strong; }
QTableWidget { background: @table; border: 1px solid @border; border-radius: 12px; gridline-color: @border; alternate-background-color: @alt; selection-background-color: @select; selection-color: @strong; outline: 0; }
QHeaderView { background: transparent; }
QHeaderView::section { background: @panel; color: @muted; border: 0; border-bottom: 1px solid @border; padding: 10px; font-weight: 700; }
QTableWidget::item { padding: 6px; }
QTableWidget::item:hover { background: @hover; }
QProgressBar { background: @input; border: 1px solid @border; border-radius: 6px; text-align: center; min-width: 110px; color: @text; }
QProgressBar::chunk { background: @blue; border-radius: 5px; }
QProgressBar[state="ok"]::chunk { background: @green; }
QProgressBar[state="warn"]::chunk { background: @amber; }
QProgressBar[state="over"]::chunk { background: @red; }
QDialog { background: @panel2; }
QStatusBar { color: @muted; background: @bg; }
QToolTip { background: @panel; color: @text; border: 1px solid @border2; padding: 6px; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: @border2; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: @muted; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px; }
QScrollBar::handle:horizontal { background: @border2; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QFrame#toast { background: @toast; border: 1px solid @border2; border-radius: 12px; }
QFrame#toast[kind="ok"] { border-left: 4px solid @green; }
QFrame#toast[kind="warn"] { border-left: 4px solid @amber; }
QFrame#toast[kind="info"] { border-left: 4px solid @blue; }
QLabel#toastText { color: #f8fafc; font-weight: 600; background: transparent; }
QPushButton#toastAction { background: transparent; border: 0; color: #93c5fd; font-weight: 800; padding: 6px 10px; }
QPushButton#toastAction:hover { background: rgba(255,255,255,0.10); }
QPushButton#toastClose { background: transparent; border: 0; color: #94a3b8; padding: 6px 8px; }
QPushButton#toastClose:hover { color: #ffffff; }
"""


def apply_style(app):
    app.setFont(QFont("Segoe UI", 10))
    css = STYLE
    for key in sorted(T, key=len, reverse=True):
        if key != "name":
            css = css.replace("@" + key, T[key])
    app.setStyleSheet(css)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Personal Finance Lite")
    app.setWindowIcon(QIcon(resource_path("assets/app.ico")))
    set_theme(QSettings("PersonalFinanceLite", "Pro").value("theme", "dark"))
    apply_style(app)

    splash_pixmap = QPixmap(resource_path("assets/splash.png"))
    splash = QSplashScreen(splash_pixmap, Qt.WindowType.FramelessWindowHint)
    splash.setWindowIcon(QIcon(resource_path("assets/app.ico")))
    splash.show()
    app.processEvents()

    try:
        core.auto_backup_if_due()  # daily safety copy; never blocks startup
    except Exception:
        pass

    window = MainWindow()
    window.showMaximized()
    app.processEvents()
    splash.finish(window)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
