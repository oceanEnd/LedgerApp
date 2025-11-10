import calendar as cal
import datetime as dt
import math
import random
import shutil
import string
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ledger import LedgerStore

IOS_COLORS = {
    "background": "#F2F2F7",
    "surface": "#FFFFFF",
    "surface_alt": "#F8F9FB",
    "border": "#E5E5EA",
    "text": "#1C1C1E",
    "text_muted": "#6E6E73",
    "accent": "#4f4f4f",
    "accent_active": "#7f7f7f",
    "accent_soft": "#E3F2FF",
    "danger": "#7f7f7f",
    "danger_active": "#D70015",
    "success": "#7f7f7f",
}

NAV_ITEMS = [
    ("home", "主页"),
    ("transactions", "交易记录"),
    ("analytics", "收支统计"),
    ("categories", "类别管理"),
    ("security", "安全设置"),
]


class LedgerApp(tk.Tk):
    """Tkinter 智能记账 Demo，采用类 iOS 卡片 UI，并提供侧边导航."""

    def __init__(self) -> None:
        super().__init__()
        self.title("智能记账本 Demo")
        self.geometry("1280x760")
        self.minsize(1080, 680)
        self.configure(bg=IOS_COLORS["background"])

        self.store = LedgerStore()
        self.data_file = Path(__file__).resolve().parent / "user_data.json"
        self.editing_record_id: str | None = None
        self.active_filters: dict | None = None
        self.current_action_record_id: str | None = None
        self.edit_form_vars: dict[str, tk.StringVar] | None = None

        self.pages: dict[str, ttk.Frame] = {}
        self.nav_items: dict[str, dict[str, object]] = {}
        self.active_nav: str = "home"

        self.edit_window: tk.Toplevel | None = None
        self.toast_window: tk.Toplevel | None = None
        self.toast_alpha: float = 0.0
        self.calendar_window: tk.Toplevel | None = None
        self.calendar_target_var: tk.StringVar | None = None
        self.calendar_reference_date: dt.date = dt.date.today()
        self.calendar_month_label: ttk.Label | None = None
        self.calendar_days_frame: ttk.Frame | None = None
        self.theme_canvas: tk.Canvas | None = None
        self.theme_hover: bool = False

        self._setup_style()
        self._load_default_data()
        self._build_variables()
        self._build_layout()

        self.show_page("home")
        self.refresh_records()

    # ---------- 样式与布局 ----------
    def _setup_style(self) -> None:
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        self.font_regular = ("SF Pro Text", 11)
        self.font_small = ("SF Pro Text", 10)
        self.font_title = ("SF Pro Display", 14, "bold")

        self.style.configure("Background.TFrame", background=IOS_COLORS["background"])
        self.style.configure("Sidebar.TFrame", background=IOS_COLORS["surface"], borderwidth=0)
        self.style.configure("Card.TFrame", background=IOS_COLORS["surface"], relief="flat", borderwidth=0)
        self.style.configure("CardBody.TFrame", background=IOS_COLORS["surface"])
        self.style.configure("CardTitle.TLabel", background=IOS_COLORS["surface"], foreground=IOS_COLORS["text"], font=self.font_title)
        self.style.configure("SidebarTitle.TLabel", background=IOS_COLORS["surface"], foreground=IOS_COLORS["text"], font=("SF Pro Display", 18, "bold"))
        self.style.configure("TLabel", background=IOS_COLORS["surface"], foreground=IOS_COLORS["text"], font=self.font_regular)
        self.style.configure("Small.TLabel", background=IOS_COLORS["surface"], foreground=IOS_COLORS["text_muted"], font=self.font_small)
        self.style.configure(
            "Summary.TLabel",
            background=IOS_COLORS["surface"],
            foreground=IOS_COLORS["text_muted"],
            font=("SF Pro Text", 11, "bold"),
        )

        entry_opts = {
            "fieldbackground": IOS_COLORS["surface_alt"],
            "background": IOS_COLORS["surface_alt"],
            "foreground": IOS_COLORS["text"],
            "bordercolor": IOS_COLORS["border"],
            "padding": (10, 6),
        }
        self.style.configure("Modern.TEntry", **entry_opts)
        self.style.map("Modern.TEntry", fieldbackground=[("focus", IOS_COLORS["surface"])])

        combo_opts = entry_opts | {"arrowsize": 12}
        self.style.configure("Modern.TCombobox", **combo_opts)
        self.style.map("Modern.TCombobox", fieldbackground=[("readonly", IOS_COLORS["surface_alt"])])

        self.style.configure(
            "Accent.TButton",
            background=IOS_COLORS["accent"],
            foreground="#FFFFFF",
            borderwidth=0,
            focusthickness=0,
            padding=(18, 8),
            font=("SF Pro Text", 11, "bold"),
        )
        self.style.map("Accent.TButton", background=[("active", IOS_COLORS["accent_active"])])

        self.style.configure(
            "Ghost.TButton",
            background=IOS_COLORS["surface_alt"],
            foreground=IOS_COLORS["accent"],
            borderwidth=1,
            bordercolor=IOS_COLORS["accent"],
            padding=(16, 8),
            focusthickness=0,
        )
        self.style.map("Ghost.TButton", background=[("active", IOS_COLORS["accent_soft"])])

        self.style.configure(
            "Nav.TButton",
            background=IOS_COLORS["surface"],
            foreground=IOS_COLORS["text"],
            font=("SF Pro Text", 12),
            padding=(16, 10),
            anchor="w",
        )
        self.style.configure(
            "NavActive.TButton",
            background=IOS_COLORS["accent_active"],
            foreground=IOS_COLORS["text"],
            font=("SF Pro Text", 12, "bold"),
            padding=(16, 10),
            anchor="w",
        )

        self.style.configure(
            "Ledger.Treeview",
            background=IOS_COLORS["surface"],
            fieldbackground=IOS_COLORS["surface"],
            foreground=IOS_COLORS["text"],
            rowheight=36,
            bordercolor=IOS_COLORS["border"],
            font=self.font_regular,
        )
        self.style.configure(
            "Ledger.Treeview.Heading",
            background=IOS_COLORS["surface"],
            foreground=IOS_COLORS["text_muted"],
            font=("SF Pro Text", 11, "bold"),
            relief="flat",
        )
        self.style.map("Ledger.Treeview", background=[("selected", IOS_COLORS["accent"])], foreground=[("selected", "#FFFFFF")])

    def _build_variables(self) -> None:
        today = dt.date.today().isoformat()
        self.amount_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.category_type_var = tk.StringVar(value="expense")
        self.date_var = tk.StringVar(value=today)

        self.search_start_var = tk.StringVar()
        self.search_end_var = tk.StringVar()
        self.search_category_var = tk.StringVar()
        self.search_min_var = tk.StringVar()
        self.search_max_var = tk.StringVar()

        self.summary_text = tk.StringVar(value="收支汇总：收入 ¥0.00 / 支出 ¥0.00 / 结余 ¥0.00")
        self._reset_filter_defaults()

    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self, style="Sidebar.TFrame", padding=(18, 28, 12, 28))
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.configure(width=250)
        sidebar.grid_propagate(False)
        sidebar.rowconfigure(len(NAV_ITEMS) + 1, weight=1)
        self._build_sidebar(sidebar)

        content = ttk.Frame(self, style="Background.TFrame")
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        self.content = content

        self._build_home_page()
        self._build_transactions_page()
        self._build_analytics_page()
        self._build_category_page()
        self._build_security_page()

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        ttk.Label(parent, text="智能记账本系统", style="SidebarTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 24))
        for idx, (key, label) in enumerate(NAV_ITEMS, start=1):
            canvas = tk.Canvas(
                parent,
                height=46,
                bd=0,
                highlightthickness=0,
                bg=IOS_COLORS["surface"],
                cursor="hand2",
            )
            canvas.grid(row=idx, column=0, sticky="ew", pady=4)
            text_id = canvas.create_text(
                32,
                23,
                text=label,
                anchor="w",
                font=("SF Pro Text", 12),
                fill=IOS_COLORS["text"],
            )
            self.nav_items[key] = {"canvas": canvas, "text": text_id, "hover": False}
            canvas.bind("<Enter>", lambda _e, k=key: self._set_nav_hover(k, True))
            canvas.bind("<Leave>", lambda _e, k=key: self._set_nav_hover(k, False))
            canvas.bind("<Button-1>", lambda _e, k=key: self.show_page(k))
            canvas.bind("<Configure>", lambda _e, k=key: self._render_nav_item(k))
        parent.rowconfigure(len(NAV_ITEMS) + 1, weight=1)

        theme_canvas = tk.Canvas(
            parent,
            height=44,
            bd=0,
            highlightthickness=0,
            bg=IOS_COLORS["surface"],
            cursor="hand2",
        )
        theme_canvas.grid(row=len(NAV_ITEMS) + 2, column=0, sticky="ew", pady=(24, 0))
        theme_canvas.create_text(
            32,
            22,
            text="日/夜模式（TODO）",
            anchor="w",
            font=("SF Pro Text", 11),
            fill=IOS_COLORS["text_muted"],
            tags="label",
        )
        self.theme_canvas = theme_canvas
        theme_canvas.bind("<Enter>", lambda _e: self._set_theme_hover(True))
        theme_canvas.bind("<Leave>", lambda _e: self._set_theme_hover(False))
        theme_canvas.bind("<Button-1>", lambda _e: self.show_toast("TODO - 该功能未完成"))
        theme_canvas.bind("<Configure>", lambda _e: self._render_theme_toggle())
        self._refresh_nav_styles()

    def _set_nav_hover(self, key: str, hover: bool) -> None:
        item = self.nav_items.get(key)
        if not item or item["hover"] == hover:
            return
        item["hover"] = hover
        self._render_nav_item(key)

    def _render_nav_item(self, key: str) -> None:
        item = self.nav_items.get(key)
        if not item:
            return
        canvas = item["canvas"]
        canvas.delete("bg")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 0 or height <= 0:
            return
        color = None
        if key == self.active_nav:
            color = IOS_COLORS["text"]
        elif item["hover"]:
            color = IOS_COLORS["border"]
        if color:
            self._draw_round_rect(canvas, 8, 6, width - 8, height - 6, 16, fill=color, outline="", tags="bg")
            canvas.tag_lower("bg")
        text_color = "#FFFFFF" if key == self.active_nav else IOS_COLORS["text"]
        canvas.itemconfig(item["text"], fill=text_color)

    def _refresh_nav_styles(self) -> None:
        for key in self.nav_items:
            self._render_nav_item(key)

    def _set_theme_hover(self, hover: bool) -> None:
        if self.theme_hover == hover:
            return
        self.theme_hover = hover
        self._render_theme_toggle()

    def _render_theme_toggle(self) -> None:
        if not self.theme_canvas:
            return
        canvas = self.theme_canvas
        canvas.delete("bg")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 0 or height <= 0:
            return
        if self.theme_hover:
            self._draw_round_rect(canvas, 8, 6, width - 8, height - 6, 16, fill=IOS_COLORS["surface_alt"], outline="", tags="bg")
            canvas.tag_lower("bg")

    def _draw_round_rect(
        self,
        canvas: tk.Canvas,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        radius: float,
        **kwargs,
    ) -> None:
        if x2 <= x1 or y2 <= y1:
            return
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        canvas.create_polygon(points, smooth=True, splinesteps=36, **kwargs)

    def _center_popup(self, window: tk.Toplevel) -> None:
        self.update_idletasks()
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        if width <= 0 or height <= 0:
            width = 300
            height = 200
        x = self.winfo_rootx() + (self.winfo_width() - width) // 2
        y = self.winfo_rooty() + (self.winfo_height() - height) // 2
        window.geometry(f"+{x}+{y}")

    def _build_home_page(self) -> None:
        page = ttk.Frame(self.content, style="Background.TFrame", padding=32)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=2)
        page.columnconfigure(1, weight=1)
        self.pages["home"] = page

        form_card = self._create_card(page, "记一笔", row=0, column=0, sticky="nsew", padx=(0, 16))
        self._build_record_form(form_card)

        tools_card = self._create_card(page, "数据工具", row=0, column=1, sticky="nsew")
        self._build_data_tools(tools_card)

    def _build_transactions_page(self) -> None:
        page = ttk.Frame(self.content, style="Background.TFrame", padding=32)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        self.pages["transactions"] = page

        filter_card = self._create_card(page, "筛选条件", row=0, column=0, sticky="ew", pady=(0, 16))
        self._build_filter_bar(filter_card)

        table_card = self._create_card(page, "交易列表", row=1, column=0, sticky="nsew")
        self._build_transaction_table(table_card)

    def _build_analytics_page(self) -> None:
        page = ttk.Frame(self.content, style="Background.TFrame", padding=32)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        page.rowconfigure(1, weight=10)
        self.pages["analytics"] = page

        self.analytics_summary_vars = {
            "income": tk.StringVar(value="¥0.00"),
            "expense": tk.StringVar(value="¥0.00"),
            "balance": tk.StringVar(value="¥0.00"),
        }

        summary_frame = ttk.Frame(page, style="Background.TFrame")
        summary_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 30))
        summary_frame.rowconfigure(0, weight=1)
        for idx in range(3):
            summary_frame.columnconfigure(idx, weight=1)
        summary_labels = [
            ("income", "总收入"),
            ("expense", "总支出"),
            ("balance", "结余"),
        ]
        for idx, (key, title) in enumerate(summary_labels):
            card = self._create_card(
                summary_frame,
                title,
                row=0,
                column=idx,
                sticky="nsew",
                padx=(0 if idx == 0 else 30, 0),
            )
            ttk.Label(
                card,
                textvariable=self.analytics_summary_vars[key],
                font=("SF Pro Display", 35, "bold"),
                background=IOS_COLORS["surface"],
                foreground=IOS_COLORS["text"],
            ).pack(anchor="center", pady=12)

        chart_card = self._create_card(page, "收支图表", row=1, column=0, sticky="nsew")
        chart_card.columnconfigure(0, weight=1)
        chart_card.columnconfigure(1, weight=1)
        chart_card.rowconfigure(0, weight=1)

        self.bar_canvas = tk.Canvas(chart_card, bg=IOS_COLORS["surface_alt"], height=150, highlightthickness=0)
        self.bar_canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 60))
        self.bar_canvas.bind("<Configure>", lambda _e: self.draw_bar_chart())

        self.pie_canvas = tk.Canvas(chart_card, bg=IOS_COLORS["surface_alt"], height=150, highlightthickness=0)
        self.pie_canvas.grid(row=0, column=1, sticky="nsew")
        self.pie_canvas.bind("<Configure>", lambda _e: self.draw_pie_chart())


    def _build_security_page(self) -> None:
        page = ttk.Frame(self.content, style="Background.TFrame", padding=32)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        self.pages["security"] = page

        placeholder = self._create_card(page, "安全设置", row=0, column=0, sticky="nsew")
        ttk.Label(placeholder, text="应用锁、权限管理等功能将在后续版本提供。", style="Small.TLabel").pack(expand=True, fill=tk.BOTH)

    def _build_category_page(self) -> None:
        page = ttk.Frame(self.content, style="Background.TFrame", padding=32)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)
        self.pages["categories"] = page

        placeholder = self._create_card(page, "类别管理", row=0, column=0, sticky="nsew")
        ttk.Label(placeholder, text="TODO：类别管理功能尚未完成。", style="Small.TLabel").pack(expand=True, fill=tk.BOTH)

    # ---------- 组件构建 ----------
    def _create_card(self, parent: ttk.Frame, title: str, row: int, column: int, **grid) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=(20, 18))
        pady = grid.pop("pady", (0, 0))
        padx = grid.pop("padx", (0, 0))
        sticky = grid.pop("sticky", "nsew")
        card.grid(row=row, column=column, sticky=sticky, pady=pady, padx=padx)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(1, weight=1)

        ttk.Label(card, text=title, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 12))
        body = ttk.Frame(card, style="CardBody.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        return body

    def _build_record_form(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="金额 (¥)").grid(row=0, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.amount_var, style="Modern.TEntry").grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="分类").grid(row=1, column=0, sticky="w")
        self.category_combo = ttk.Combobox(
            parent,
            textvariable=self.category_var,
            values=[name for name, _ in self.store.get_categories()],
            style="Modern.TCombobox",
        )
        self.category_combo.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="类型").grid(row=2, column=0, sticky="w")
        type_frame = ttk.Frame(parent, style="CardBody.TFrame")
        type_frame.grid(row=2, column=1, sticky="w", pady=4)
        ttk.Radiobutton(
            type_frame,
            text="支出",
            value="expense",
            variable=self.category_type_var,
            takefocus=0,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            type_frame,
            text="收入",
            value="income",
            variable=self.category_type_var,
            takefocus=0,
        ).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(parent, text="日期 (YYYY-MM-DD)").grid(row=3, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.date_var, style="Modern.TEntry").grid(row=3, column=1, sticky="ew", pady=4)

        btn_frame = ttk.Frame(parent, style="CardBody.TFrame")
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(18, 0), sticky="ew")
        ttk.Button(
            btn_frame,
            text="保存",
            style="Accent.TButton",
            command=self.save_record,
            takefocus=0,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(
            btn_frame,
            text="清空",
            style="Ghost.TButton",
            command=self.reset_form,
            takefocus=0,
        ).pack(side=tk.LEFT, padx=(10, 0))

    def _build_data_tools(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="导入其他设备的账本数据或导出备份。", style="Small.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 12))
        btn_frame = ttk.Frame(parent, style="CardBody.TFrame")
        btn_frame.grid(row=1, column=0, sticky="ew")
        ttk.Button(btn_frame, text="导入 JSON", style="Ghost.TButton", command=self.import_json, takefocus=0).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(btn_frame, text="导出 JSON", style="Ghost.TButton", command=self.export_json, takefocus=0).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(12, 0))

    def _reset_filter_defaults(self) -> None:
        start = dt.date.today().replace(day=1)
        end = dt.date.today()
        self.search_start_var.set(start.isoformat())
        self.search_end_var.set(end.isoformat())

    def _build_filter_bar(self, parent: ttk.Frame) -> None:
        for col in range(4):
            parent.columnconfigure(col, weight=1)

        ttk.Label(parent, text="开始日期").grid(row=0, column=0, sticky="w")
        self._create_date_input(parent, self.search_start_var, row=0, column=1)
        ttk.Label(parent, text="结束日期").grid(row=0, column=2, sticky="w")
        self._create_date_input(parent, self.search_end_var, row=0, column=3)

        ttk.Label(parent, text="分类").grid(row=1, column=0, sticky="w")
        self.filter_category_combo = ttk.Combobox(
            parent,
            textvariable=self.search_category_var,
            values=[""] + [name for name, _ in self.store.get_categories()],
            style="Modern.TCombobox",
        )
        self.filter_category_combo.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(parent, text="最低金额").grid(row=1, column=2, sticky="w")
        ttk.Entry(parent, textvariable=self.search_min_var, style="Modern.TEntry").grid(row=1, column=3, sticky="ew", pady=4)

        ttk.Label(parent, text="最高金额").grid(row=2, column=2, sticky="w")
        ttk.Entry(parent, textvariable=self.search_max_var, style="Modern.TEntry").grid(row=2, column=3, sticky="ew", pady=4)

        btn_frame = ttk.Frame(parent, style="CardBody.TFrame")
        btn_frame.grid(row=3, column=0, columnspan=4, pady=(16, 0), sticky="ew")
        ttk.Button(
            btn_frame,
            text="搜索",
            style="Accent.TButton",
            command=self.perform_search,
            takefocus=0,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(
            btn_frame,
            text="重置",
            style="Ghost.TButton",
            command=self.clear_filters,
            takefocus=0,
        ).pack(side=tk.LEFT, padx=(10, 0))

    def _create_date_input(self, parent: ttk.Frame, variable: tk.StringVar, row: int, column: int) -> None:
        field = ttk.Frame(parent, style="CardBody.TFrame")
        field.grid(row=row, column=column, sticky="ew", pady=4)
        ttk.Entry(field, textvariable=variable, style="Modern.TEntry").pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            field,
            text="日历",
            style="Ghost.TButton",
            command=lambda v=variable: self.open_calendar(v),
            width=6,
            takefocus=0,
        ).pack(side=tk.LEFT, padx=(8, 0))

    # ---------- 日历选择 ----------
    def open_calendar(self, target_var: tk.StringVar) -> None:
        if self.calendar_window and self.calendar_window.winfo_exists():
            self.calendar_window.destroy()
        self.calendar_target_var = target_var
        try:
            self.calendar_reference_date = self.parse_date(target_var.get())
        except ValueError:
            self.calendar_reference_date = dt.date.today()
        window = tk.Toplevel(self)
        window.title("选择日期")
        window.transient(self)
        window.resizable(False, False)
        window.configure(bg=IOS_COLORS["background"])
        window.protocol("WM_DELETE_WINDOW", self._close_calendar)
        self.calendar_window = window

        container = ttk.Frame(window, padding=16, style="Background.TFrame")
        container.grid(row=0, column=0, sticky="nsew")

        header = ttk.Frame(container, style="Background.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Button(
            header,
            text="<",
            style="Ghost.TButton",
            command=lambda: self._shift_calendar(-1),
            width=3,
            takefocus=0,
        ).grid(row=0, column=0, padx=(0, 8))
        self.calendar_month_label = ttk.Label(header, text="", style="CardTitle.TLabel")
        self.calendar_month_label.grid(row=0, column=1, sticky="n")
        ttk.Button(
            header,
            text=">",
            style="Ghost.TButton",
            command=lambda: self._shift_calendar(1),
            width=3,
            takefocus=0,
        ).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(
            header,
            text="今天",
            style="Ghost.TButton",
            command=self._select_today,
            takefocus=0,
        ).grid(row=0, column=3, padx=(12, 0))

        self.calendar_days_frame = ttk.Frame(container, style="Background.TFrame")
        self.calendar_days_frame.grid(row=1, column=0, sticky="nsew", pady=(12, 0))

        self._render_calendar_days()
        self._center_popup(window)
        window.grab_set()

    def _shift_calendar(self, months: int) -> None:
        if not self.calendar_window:
            return
        year = self.calendar_reference_date.year
        month = self.calendar_reference_date.month + months
        year += (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(self.calendar_reference_date.day, cal.monthrange(year, month)[1])
        self.calendar_reference_date = dt.date(year, month, day)
        self._render_calendar_days()

    def _render_calendar_days(self) -> None:
        if not self.calendar_days_frame:
            return
        for child in self.calendar_days_frame.winfo_children():
            child.destroy()
        if self.calendar_month_label:
            self.calendar_month_label.configure(text=self.calendar_reference_date.strftime("%Y年%m月"))
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        for idx, name in enumerate(weekdays):
            ttk.Label(
                self.calendar_days_frame,
                text=name,
                style="Small.TLabel",
                padding=4,
            ).grid(row=0, column=idx, padx=2, pady=2)
        year = self.calendar_reference_date.year
        month = self.calendar_reference_date.month
        first_weekday, days_in_month = cal.monthrange(year, month)
        row = 1
        col = first_weekday
        for _ in range(first_weekday):
            ttk.Label(self.calendar_days_frame, text="", style="Small.TLabel", padding=4).grid(row=row, column=_, padx=2, pady=2)
        for day in range(1, days_in_month + 1):
            ttk.Button(
                self.calendar_days_frame,
                text=str(day),
                style="Ghost.TButton",
                command=lambda d=day: self._select_calendar_day(d),
                width=4,
                takefocus=0,
            ).grid(row=row, column=col, padx=2, pady=2)
            col += 1
            if col > 6:
                col = 0
                row += 1

    def _select_calendar_day(self, day: int) -> None:
        if not self.calendar_target_var:
            return
        selected = dt.date(self.calendar_reference_date.year, self.calendar_reference_date.month, day)
        self.calendar_target_var.set(selected.isoformat())
        self._close_calendar()

    def _select_today(self) -> None:
        today = dt.date.today()
        self.calendar_reference_date = today
        if self.calendar_target_var:
            self.calendar_target_var.set(today.isoformat())
        self._close_calendar()

    def _close_calendar(self) -> None:
        if self.calendar_window and self.calendar_window.winfo_exists():
            self.calendar_window.destroy()
        self.calendar_window = None
        self.calendar_target_var = None
        self.calendar_month_label = None
        self.calendar_days_frame = None

    def _build_transaction_table(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        columns = ("date", "category", "type", "amount", "action")
        self.transaction_tree = ttk.Treeview(parent, columns=columns, show="headings", style="Ledger.Treeview")
        self.transaction_tree.heading("date", text="日期")
        self.transaction_tree.heading("category", text="分类")
        self.transaction_tree.heading("type", text="类型")
        self.transaction_tree.heading("amount", text="金额")
        self.transaction_tree.heading("action", text="操作")
        self.transaction_tree.column("date", width=110, anchor="center")
        self.transaction_tree.column("category", width=160, anchor="center")
        self.transaction_tree.column("type", width=80, anchor="center")
        self.transaction_tree.column("amount", width=110, anchor="e")
        self.transaction_tree.column("action", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.transaction_tree.yview)
        self.transaction_tree.configure(yscrollcommand=scrollbar.set)
        self.transaction_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.transaction_tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.transaction_tree.bind("<Button-1>", self.on_tree_click)

        ttk.Label(parent, textvariable=self.summary_text, style="Summary.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 0))

    # ---------- 页面切换 ----------
    def show_page(self, key: str) -> None:
        page = self.pages.get(key)
        if not page:
            return
        page.tkraise()
        self.active_nav = key
        self._refresh_nav_styles()
        if key == "analytics":
            self.draw_charts()
        elif key == "transactions":
            self.refresh_records()
        if key == "categories":
            self.show_toast("TODO - 类别管理功能未完成")

    # ---------- 业务操作 ----------
    def parse_date(self, value: str) -> dt.date:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()

    def save_record(self) -> None:
        try:
            amount = float(self.amount_var.get())
        except ValueError:
            messagebox.showerror("提示", "请输入合法金额")
            return
        if amount < 0:
            messagebox.showwarning("提示", "金额必须大于等于 0")
            return
        if not self.category_var.get():
            messagebox.showwarning("提示", "请选择或输入分类")
            return
        try:
            date_obj = self.parse_date(self.date_var.get())
        except ValueError:
            messagebox.showerror("提示", "日期格式应为 YYYY-MM-DD")
            return

        action = "新增"
        if self.editing_record_id:
            self.store.update_record(
                self.editing_record_id,
                amount,
                self.category_var.get(),
                self.category_type_var.get(),
                date_obj,
            )
            action = "编辑"
        else:
            self.store.add_record(
                amount,
                self.category_var.get(),
                self.category_type_var.get(),
                date_obj,
            )
        self.update_category_inputs()
        self.refresh_records()
        if self.persist_data():
            self.show_toast(f"{action}成功")
        self.reset_form()
        self.show_page("transactions")

    def reset_form(self) -> None:
        self.amount_var.set("")
        self.category_var.set("")
        self.category_type_var.set("expense")
        self.date_var.set(dt.date.today().isoformat())
        self.editing_record_id = None

    def on_tree_select(self, _event: tk.Event) -> None:
        selection = self.transaction_tree.selection()
        if not selection:
            return
        record_id = selection[0]
        record = self.store.find_record(record_id)
        if not record:
            return
        self.editing_record_id = record.id

    def on_tree_click(self, event: tk.Event) -> None:
        region = self.transaction_tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = self.transaction_tree.identify_row(event.y)
        column = self.transaction_tree.identify_column(event.x)
        if column == "#5" and row_id:
            self.transaction_tree.selection_set(row_id)
            self.open_action_menu(row_id, event.x_root, event.y_root)

    def open_action_menu(self, record_id: str, x_root: int, y_root: int) -> None:
        self.current_action_record_id = record_id
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="编辑", command=self.edit_record_from_menu)
        menu.add_command(label="删除", command=self.delete_record_from_menu)
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def edit_record_from_menu(self) -> None:
        if not self.current_action_record_id:
            return
        record = self.store.find_record(self.current_action_record_id)
        if not record:
            return
        self._open_edit_window(record)

    def _open_edit_window(self, record) -> None:
        if self.edit_window and self.edit_window.winfo_exists():
            self.edit_window.destroy()
        self.edit_form_vars = {
            "amount": tk.StringVar(value=str(record.amount)),
            "category": tk.StringVar(value=record.category),
            "type": tk.StringVar(value=record.category_type),
            "date": tk.StringVar(value=record.date.isoformat()),
        }
        window = tk.Toplevel(self)
        window.title("编辑记录")
        window.transient(self)
        window.resizable(False, False)
        window.configure(bg=IOS_COLORS["background"])
        window.protocol("WM_DELETE_WINDOW", self._close_edit_window)
        container = ttk.Frame(window, padding=24, style="Background.TFrame")
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(1, weight=1)

        ttk.Label(container, text="金额 (¥)").grid(row=0, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.edit_form_vars["amount"], style="Modern.TEntry").grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(container, text="分类").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            container,
            textvariable=self.edit_form_vars["category"],
            values=[name for name, _ in self.store.get_categories()],
            style="Modern.TCombobox",
        ).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(container, text="类型").grid(row=2, column=0, sticky="w")
        type_frame = ttk.Frame(container, style="Background.TFrame")
        type_frame.grid(row=2, column=1, sticky="w", pady=4)
        ttk.Radiobutton(
            type_frame,
            text="支出",
            value="expense",
            variable=self.edit_form_vars["type"],
            takefocus=0,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            type_frame,
            text="收入",
            value="income",
            variable=self.edit_form_vars["type"],
            takefocus=0,
        ).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(container, text="日期 (YYYY-MM-DD)").grid(row=3, column=0, sticky="w")
        ttk.Entry(container, textvariable=self.edit_form_vars["date"], style="Modern.TEntry").grid(row=3, column=1, sticky="ew", pady=4)

        btn_frame = ttk.Frame(container, style="Background.TFrame")
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(18, 0), sticky="ew")
        ttk.Button(
            btn_frame,
            text="保存修改",
            style="Accent.TButton",
            command=lambda rid=record.id: self._submit_edit_window(rid),
            takefocus=0,
        ).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(
            btn_frame,
            text="取消",
            style="Ghost.TButton",
            command=self._close_edit_window,
            takefocus=0,
        ).pack(side=tk.LEFT, padx=(12, 0))

        self._center_popup(window)
        window.grab_set()
        self.edit_window = window

    def _submit_edit_window(self, record_id: str) -> None:
        if not self.edit_form_vars:
            return
        try:
            amount = float(self.edit_form_vars["amount"].get())
        except ValueError:
            messagebox.showerror("提示", "请输入合法金额")
            return
        if amount < 0:
            messagebox.showwarning("提示", "金额必须大于等于 0")
            return
        category = self.edit_form_vars["category"].get()
        if not category:
            messagebox.showwarning("提示", "请选择或输入分类")
            return
        try:
            date_obj = self.parse_date(self.edit_form_vars["date"].get())
        except ValueError:
            messagebox.showerror("提示", "日期格式应为 YYYY-MM-DD")
            return
        self.store.update_record(
            record_id,
            amount,
            category,
            self.edit_form_vars["type"].get(),
            date_obj,
        )
        self.update_category_inputs()
        self.refresh_records()
        if self.persist_data():
            self.show_toast("编辑成功")
        self._close_edit_window()

    def _close_edit_window(self) -> None:
        if self.edit_window and self.edit_window.winfo_exists():
            self.edit_window.destroy()
        self.edit_window = None
        self.edit_form_vars = None

    def delete_record_from_menu(self) -> None:
        if not self.current_action_record_id:
            return
        if messagebox.askyesno("确认", "确定删除该条记录吗？"):
            self.store.delete_record(self.current_action_record_id)
            self.refresh_records()
            self.reset_form()
            if self.persist_data():
                self.show_toast("删除成功")

    def perform_search(self) -> None:
        filters: dict = {}
        try:
            if self.search_start_var.get():
                filters["start_date"] = self.parse_date(self.search_start_var.get())
            if self.search_end_var.get():
                filters["end_date"] = self.parse_date(self.search_end_var.get())
        except ValueError:
            messagebox.showerror("提示", "搜索日期格式需为 YYYY-MM-DD")
            return
        category = self.search_category_var.get().strip()
        if category:
            filters["category"] = category
        try:
            if self.search_min_var.get():
                filters["min_amount"] = float(self.search_min_var.get())
            if self.search_max_var.get():
                filters["max_amount"] = float(self.search_max_var.get())
        except ValueError:
            messagebox.showerror("提示", "金额筛选请输入数字")
            return
        self.refresh_records(filters)

    def clear_filters(self) -> None:
        self._reset_filter_defaults()
        self.search_category_var.set("")
        self.search_min_var.set("")
        self.search_max_var.set("")
        self.refresh_records({})

    def refresh_records(self, filters: dict | None = None) -> None:
        if filters is not None:
            self.active_filters = filters if filters else None
        records = self.store.search_records(**(self.active_filters or {}))
        if not hasattr(self, "transaction_tree"):
            return
        for row in self.transaction_tree.get_children():
            self.transaction_tree.delete(row)
        for record in records:
            display_amount = f"{record.amount:.2f}"
            if record.category_type == "expense":
                display_amount = f"-{display_amount}"
            else:
                display_amount = f"+{display_amount}"
            self.transaction_tree.insert(
                "",
                tk.END,
                iid=record.id,
                values=(
                    record.date.isoformat(),
                    record.category,
                    "收入" if record.category_type == "income" else "支出",
                    display_amount,
                    "...",
                ),
            )
        income = sum(r.amount for r in records if r.category_type == "income")
        expense = sum(r.amount for r in records if r.category_type == "expense")
        balance = income - expense
        self.summary_text.set(
            f"收支汇总：收入 ¥{income:.2f} / 支出 ¥{expense:.2f} / 结余 ¥{balance:.2f}"
        )
        self.update_analytics_summary()
        self.draw_charts()

    # ---------- 图表 ----------
    def draw_charts(self) -> None:
        if hasattr(self, "bar_canvas"):
            self.draw_bar_chart()
        if hasattr(self, "pie_canvas"):
            self.draw_pie_chart()

    def draw_bar_chart(self) -> None:
        self.bar_canvas.delete("all")
        data = self.store.monthly_trend(12)
        width = max(int(self.bar_canvas.winfo_width()), 320)
        height = max(int(self.bar_canvas.winfo_height()), 220)
        if not data:
            self.bar_canvas.create_text(
                width / 2,
                height / 2,
                text="暂无数据",
                fill=IOS_COLORS["text_muted"],
                font=self.font_regular,
            )
            return
        values = [abs(amount) for _, amount in data]
        max_value = max(values) or 1
        padding = 15
        bar_width = (width - padding * 2) / len(data) * 1.0
        mid_y = height / 2
        max_bar_height = (height - padding * 2) * 0.13
        self.bar_canvas.create_line(
            padding,
            mid_y,
            width - padding,
            mid_y,
            fill=IOS_COLORS["border"],
            width=1.2,
        )
        unit = 1000
        guide_color = "#D7DBE7"
        max_line = max(max_value, 4000)
        if max_line >= unit:
            level = unit
            while level <= max_line:
                offset = (level / max_value) * max_bar_height
                y_up = mid_y - offset
                y_down = mid_y + offset
                self.bar_canvas.create_line(
                    padding,
                    y_up,
                    width - padding,
                    y_up,
                    fill=guide_color,
                    dash=(3, 4),
                )
                self.bar_canvas.create_line(
                    padding,
                    y_down,
                    width - padding,
                    y_down,
                    fill=guide_color,
                    dash=(3, 4),
                )
                self.bar_canvas.create_text(
                    padding + 4,
                    y_up - 6,
                    text=f"+{level}",
                    anchor="w",
                    fill=IOS_COLORS["text_muted"],
                    font=self.font_small,
                )
                self.bar_canvas.create_text(
                    padding + 4,
                    y_down + 6,
                    text=f"-{level}",
                    anchor="w",
                    fill=IOS_COLORS["text_muted"],
                    font=self.font_small,
                )
                level += unit

        for idx, (label, amount) in enumerate(data):
            x0 = padding + idx * bar_width + 5
            x1 = x0 + bar_width - 10
            bar_height = (abs(amount) / max_value) * max_bar_height
            if amount >= 0:
                y0 = mid_y
                y1 = mid_y - bar_height
                color = IOS_COLORS["success"]
                label_y = y1 - 12
            else:
                y0 = mid_y
                y1 = mid_y + bar_height
                color = IOS_COLORS["danger"]
                label_y = y1 + 12
            self.bar_canvas.create_rectangle(x0, y0, x1, y1, fill=color, width=0, outline=color)
            self.bar_canvas.create_text(
                (x0 + x1) / 2,
                mid_y + 18,
                text=label,
                angle=45,
                fill=IOS_COLORS["text_muted"],
                font=self.font_small,
            )
            self.bar_canvas.create_text(
                (x0 + x1) / 2,
                label_y,
                text=f"{amount:.0f}",
                fill=IOS_COLORS["text"],
                font=self.font_small,
            )

    def draw_pie_chart(self) -> None:
        self.pie_canvas.delete("all")
        data = self.store.current_month_breakdown("expense")
        width = max(int(self.pie_canvas.winfo_width()), 320)
        height = max(int(self.pie_canvas.winfo_height()), 220)
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - 40

        if not data:
            self.pie_canvas.create_text(
                center_x,
                center_y,
                text="本月暂无支出",
                fill=IOS_COLORS["text_muted"],
                font=self.font_regular,
            )
            return

        total = sum(amount for _, amount in data)
        if total == 0:
            return

        palette = ["#0A84FF", "#64D2FF", "#30D158", "#FFD60A", "#FF9F0A", "#FF453A", "#BF5AF2", "#5E5CE6"]

        if len(data) == 1:
            category, _ = data[0]
            color = palette[0]
            self.pie_canvas.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                fill=color,
                outline="white",
            )
            self.pie_canvas.create_text(
                center_x,
                center_y,
                text=f"{category}\n100%",
                fill="#FFFFFF",
                font=("SF Pro Display", 12, "bold"),
            )
            return

        start_angle = -90
        for idx, (category, amount) in enumerate(data):
            extent = amount / total * 360
            if extent >= 360:
                extent = 359.9
            color = palette[idx % len(palette)]
            self.pie_canvas.create_arc(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                start=start_angle,
                extent=extent,
                fill=color,
                outline="white",
            )
            mid_angle = math.radians(start_angle + extent / 2)
            label_radius = radius + 15
            label_x = center_x + label_radius * math.cos(mid_angle)
            label_y = center_y - label_radius * math.sin(mid_angle)
            offset = 12 if math.cos(mid_angle) >= 0 else -12
            label_x += offset
            percentage = amount / total * 100
            self.pie_canvas.create_text(
                label_x,
                label_y,
                text=f"{category}\n{percentage:.1f}%",
                fill=IOS_COLORS["text"],
                font=self.font_small,
                justify="center",
            )
            start_angle += extent

    # ---------- 反馈提示 ----------
    def show_toast(self, message: str) -> None:
        if self.toast_window and self.toast_window.winfo_exists():
            self.toast_window.destroy()
        toast = tk.Toplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast_bg = "#3C3C43"
        toast_fg = "#FFFFFF"
        frame = tk.Frame(toast, bg=toast_bg, padx=20, pady=12)
        frame.pack()
        tk.Label(frame, text=message, bg=toast_bg, fg=toast_fg, font=self.font_small).pack()
        self.toast_window = toast
        self.toast_alpha = 0.9
        toast.attributes("-alpha", self.toast_alpha)
        self._place_toast()
        toast.after(2000, self._fade_toast_step)

    def _place_toast(self) -> None:
        if not self.toast_window:
            return
        self.update_idletasks()
        width = self.toast_window.winfo_reqwidth()
        height = self.toast_window.winfo_reqheight()
        x = self.winfo_rootx() + self.winfo_width() - width - 40
        y = self.winfo_rooty() + self.winfo_height() - height - 40
        self.toast_window.geometry(f"+{x}+{y}")

    def _fade_toast_step(self) -> None:
        if not self.toast_window:
            return
        self.toast_alpha -= 0.05
        if self.toast_alpha <= 0:
            self.toast_window.destroy()
            self.toast_window = None
            return
        self.toast_window.attributes("-alpha", max(self.toast_alpha, 0))
        self.toast_window.after(80, self._fade_toast_step)

    # ---------- 数据同步 ----------
    def _load_default_data(self) -> None:
        if self.data_file.exists():
            try:
                self.store.import_json(self.data_file)
            except Exception as exc:
                messagebox.showwarning("提示", f"加载默认数据失败：{exc}")
        else:
            self.persist_data()

    def persist_data(self) -> bool:
        try:
            self.store.export_json(self.data_file)
            return True
        except Exception as exc:
            messagebox.showerror("错误", f"保存数据失败：{exc}")
            return False

    def _generate_export_filename(self) -> str:
        suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        date_str = dt.date.today().strftime("%Y%m%d")
        return f"ledger-{date_str}-{suffix}.json"

    def update_analytics_summary(self) -> None:
        if not hasattr(self, "analytics_summary_vars"):
            return
        summary = self.store.summary()
        self.analytics_summary_vars["income"].set(f"¥{summary['income']:.2f}")
        self.analytics_summary_vars["expense"].set(f"¥{summary['expense']:.2f}")
        self.analytics_summary_vars["balance"].set(f"¥{summary['balance']:.2f}")

    def update_category_inputs(self) -> None:
        values = [name for name, _ in self.store.get_categories()]
        self.category_combo.configure(values=values)
        if hasattr(self, "filter_category_combo"):
            self.filter_category_combo.configure(values=[""] + values)

    def import_json(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        try:
            src = Path(path)
            self.store.import_json(src)
            if src.resolve() != self.data_file.resolve():
                shutil.copyfile(src, self.data_file)
            self.update_category_inputs()
            self.refresh_records()
            messagebox.showinfo("提示", "导入成功")
        except Exception as exc:
            messagebox.showerror("错误", f"导入失败：{exc}")

    def export_json(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")],
            initialfile=self._generate_export_filename(),
        )
        if not path:
            return
        try:
            self.store.export_json(path)
            messagebox.showinfo("提示", "导出成功")
        except Exception as exc:
            messagebox.showerror("错误", f"导出失败：{exc}")


def main() -> None:
    app = LedgerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
