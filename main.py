"""Reddit Deal Table Tool - GUI entry point."""

import math
import re
import webbrowser
from datetime import datetime, timezone

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from config import (
    ALL_CURRENCIES,
    CURRENCY_LABELS,
    DEFAULT_CURRENCIES,
    STEAM_LABEL_MIN_PERCENT,
    STEAM_LABEL_ORDER,
)
from feed_client import fetch_and_parse
from product_index import items_to_index, resolve_urls_to_products
from table_builder import build_reddit_table
from on_sale import (
    get_on_sale_products,
    enrich_with_steam_reviews,
    _discount_str,
    _discount_pct,
    _sale_end_ms,
    _sale_end_str,
    _release_date_str,
)
from tksheet import Sheet
from steam_cache import clear as clear_steam_cache
from steam_app_list import clear_app_list_cache
from steam_appdetails_cache import clear as clear_steam_appdetails_cache


def _lerp_hex(hex_a: str, hex_b: str, t: float) -> str:
    """Linear interpolate between two hex colors; t in [0, 1]."""
    def parse(h):
        h = h.lstrip("#")
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    a, b = parse(hex_a), parse(hex_b)
    r = int(a[0] + (b[0] - a[0]) * t)
    g = int(a[1] + (b[1] - a[1]) * t)
    bl = int(a[2] + (b[2] - a[2]) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


def parse_pasted_urls(text: str) -> list[str]:
    """Split pasted text into URLs (newline or comma separated), strip whitespace."""
    urls = []
    for part in text.replace(",", "\n").splitlines():
        u = part.strip()
        if u:
            urls.append(u)
    return urls


def _apply_score_filter(rows: list[dict], filter_type: str, score_value: str, label_value: str) -> list[dict]:
    """Filter rows by score: All, Exact %, Operator (e.g. >75), or Label."""
    if filter_type == "All" or not filter_type:
        return rows
    if filter_type == "Exact %":
        try:
            target = int(score_value.strip())
        except (ValueError, TypeError):
            return rows
        return [r for r in rows if r.get("steam_percent_positive") is not None and abs(r["steam_percent_positive"] - target) <= 1]
    if filter_type == "Operator":
        s = (score_value or "").strip()
        m = re.match(r"^(>=?|<=?|==?|!=)\s*(\d+)$", s)
        if not m:
            return rows
        op, num = m.group(1), int(m.group(2))
        def ok(pct):
            if pct is None:
                return False
            if op == ">": return pct > num
            if op == ">=": return pct >= num
            if op == "<": return pct < num
            if op == "<=": return pct <= num
            if op == "==": return pct == num
            if op == "!=": return pct != num
            return False
        return [r for r in rows if ok(r.get("steam_percent_positive"))]
    if filter_type == "Label" and label_value:
        min_pct = STEAM_LABEL_MIN_PERCENT.get(label_value)
        if min_pct is None:
            return rows
        return [r for r in rows if r.get("steam_percent_positive") is not None and r["steam_percent_positive"] >= min_pct and (r.get("steam_review_desc") or "") == label_value]
    return rows


def _apply_reviews_filter(rows: list[dict], min_reviews: str) -> list[dict]:
    """Filter rows by minimum total reviews."""
    try:
        n = int((min_reviews or "").strip())
    except (ValueError, TypeError):
        return rows
    if n <= 0:
        return rows
    return [r for r in rows if (r.get("steam_total_reviews") or 0) >= n]


def _apply_discount_filter(rows: list[dict], value_str: str) -> list[dict]:
    """Filter rows by discount %: operator + number (e.g. >50, >=30). Empty = no filter."""
    s = (value_str or "").strip()
    if not s:
        return rows
    m = re.match(r"^(>=?|<=?|==?|!=)\s*(\d+)$", s)
    if not m:
        return rows
    op, num = m.group(1), int(m.group(2))

    def ok(row):
        pct = _discount_pct(row)
        if pct is None:
            return False
        if op == ">":
            return pct > num
        if op == ">=":
            return pct >= num
        if op == "<":
            return pct < num
        if op == "<=":
            return pct <= num
        if op == "==":
            return pct == num
        if op == "!=":
            return pct != num
        return False

    return [r for r in rows if ok(r)]


_ONE_DAY_MS = 86400 * 1000


def _date_str_to_start_of_day_ms(s: str) -> int | None:
    """Parse YYYY-MM-DD to start-of-day (midnight) UTC timestamp in ms, or None if invalid."""
    s = (s or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        dt = datetime(y, mo, d, 0, 0, 0, 0, tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (ValueError, OSError):
        return None


def _date_str_to_end_of_day_ms(s: str) -> int | None:
    """Parse YYYY-MM-DD to end-of-day UTC timestamp in ms, or None if invalid."""
    start = _date_str_to_start_of_day_ms(s)
    if start is None:
        return None
    return start + _ONE_DAY_MS - 1


def _parse_sale_end_value(value_str: str) -> tuple[str, int | None, int | None]:
    """
    Parse sale end filter value. Returns (mode, a, b) where:
    - mode "op": a = single date (end-of-day ms), b = None. Use with operator.
    - mode "range": a = min ms, b = max ms (both end-of-day).
    - mode "": no filter (a=b=None).
    """
    s = (value_str or "").strip()
    if not s:
        return "", None, None
    # Range: 2026-02-01..2026-02-28 or 2026-02-01 to 2026-02-28 (sale end in [min day, max day])
    range_match = re.match(r"^(\d{4}-\d{2}-\d{2})\s*(?:\.\.|to)\s*(\d{4}-\d{2}-\d{2})$", s, re.I)
    if range_match:
        lo = _date_str_to_start_of_day_ms(range_match.group(1))
        hi = _date_str_to_end_of_day_ms(range_match.group(2))
        if lo is not None and hi is not None and lo <= hi:
            return "range", lo, hi
        return "", None, None
    # Operator + date: <2026-03-01, >=2026-02-15
    op_match = re.match(r"^(>=?|<=?|==?|!=)\s*(\d{4}-\d{2}-\d{2})$", s)
    if op_match:
        date_ms = _date_str_to_end_of_day_ms(op_match.group(2))
        if date_ms is not None:
            return "op", date_ms, None
    return "", None, None


def _apply_sale_end_filter(
    rows: list[dict],
    filter_type: str,
    value_str: str,
) -> list[dict]:
    """
    Filter/sort by sale end. filter_type: All, Ending Soon, Ending Latest, By date.
    value_str used when By date: e.g. <2026-03-01 or 2026-02-01..2026-02-28.
    Rows without sale end (None) are excluded from sort and from By date; for All they stay.
    """
    if not filter_type or filter_type == "All":
        return rows
    if filter_type == "Ending Soon":
        # Sort by sale end ascending; put None at end
        return sorted(rows, key=lambda r: (_sale_end_ms(r) is None, _sale_end_ms(r) or 0))
    if filter_type == "Ending Latest":
        # Sort by sale end descending; put None at end
        return sorted(rows, key=lambda r: (_sale_end_ms(r) is None, -(_sale_end_ms(r) or 0)))
    if filter_type == "By date":
        mode, a, b = _parse_sale_end_value(value_str)
        if mode == "":
            return rows
        if mode == "op":
            op_match = re.match(r"^(>=?|<=?|==?|!=)\s*(\d{4}-\d{2}-\d{2})$", (value_str or "").strip())
            op = op_match.group(1) if op_match else "=="
            # a was end-of-day ms from parser; for op we need day boundaries
            start_ms = _date_str_to_start_of_day_ms(op_match.group(2)) if op_match else None
            if start_ms is None:
                return rows
            end_ms = start_ms + _ONE_DAY_MS - 1  # end of that day
            next_day_ms = start_ms + _ONE_DAY_MS

            def ok(row):
                ms = _sale_end_ms(row)
                if ms is None:
                    return False
                if op == "<": return ms < start_ms
                if op == "<=": return ms <= end_ms
                if op == ">": return ms >= next_day_ms
                if op == ">=": return ms >= start_ms
                if op == "==": return start_ms <= ms <= end_ms
                if op == "!=": return not (start_ms <= ms <= end_ms)
                return False
            return [r for r in rows if ok(r)]
        if mode == "range":
            def ok(row):
                ms = _sale_end_ms(row)
                if ms is None:
                    return False
                return a <= ms <= b
            return [r for r in rows if ok(r)]
    return rows


class Application:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Reddit Deal Table Tool")
        self.root.minsize(500, 450)
        self._feed_items = None
        self._index = None
        self._on_sale_rows = []  # Enriched on-sale list for tab 2
        self._tab2_displayed_rows = []  # Last rows shown (for Copy URLs)
        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Tab 1: Deal Table ---
        tab1 = ttk.Frame(notebook, padding=10)
        notebook.add(tab1, text="Deal Table")

        ttk.Label(tab1, text="Product URLs (one per line or comma-separated):").pack(anchor=tk.W)
        self.input_text = scrolledtext.ScrolledText(tab1, height=6, width=70, wrap=tk.WORD)
        self.input_text.pack(fill=tk.X, pady=(0, 8))

        btn_frame = ttk.Frame(tab1)
        btn_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(btn_frame, text="Load feed", command=self._load_feed).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="Build table", command=self._build_table).pack(side=tk.LEFT)

        ttk.Label(tab1, text="Currencies to show:").pack(anchor=tk.W, pady=(8, 4))
        curr_frame = ttk.Frame(tab1)
        curr_frame.pack(fill=tk.X)
        self.currency_vars = {}
        for i, code in enumerate(ALL_CURRENCIES):
            var = tk.BooleanVar(value=code in DEFAULT_CURRENCIES)
            self.currency_vars[code] = var
            cb = ttk.Checkbutton(curr_frame, text=CURRENCY_LABELS.get(code, code), variable=var)
            cb.grid(row=i // 6, column=i % 6, sticky=tk.W, padx=(0, 12), pady=2)
        ttk.Frame(tab1, height=8).pack()

        ttk.Label(tab1, text="Reddit markdown (copy and paste to Reddit):").pack(anchor=tk.W, pady=(8, 4))
        self.output_text = scrolledtext.ScrolledText(tab1, height=14, width=70, wrap=tk.NONE, state=tk.DISABLED)
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        ttk.Button(tab1, text="Copy to clipboard", command=self._copy_output).pack(anchor=tk.W)

        # --- Tab 2: Deal Finder ---
        tab2 = ttk.Frame(notebook, padding=10)
        notebook.add(tab2, text="Deal Finder")

        ttk.Label(tab2, text="Load the feed, then fetch on-sale products and their Steam ratings.").pack(anchor=tk.W)
        btn2 = ttk.Frame(tab2)
        btn2.pack(fill=tk.X, pady=8)
        ttk.Button(btn2, text="Load feed", command=self._load_feed_tab2).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn2, text="Fetch on-sale list & Steam data", command=self._fetch_on_sale).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn2, text="Clear Steam cache", command=self._clear_steam_cache).pack(side=tk.LEFT)
        self.tab2_status = ttk.Label(tab2, text="")
        self.tab2_status.pack(anchor=tk.W, pady=(0, 8))

        # Filters
        ttk.Label(tab2, text="Filters:").pack(anchor=tk.W, pady=(8, 4))
        filt_frame = ttk.Frame(tab2)
        filt_frame.pack(fill=tk.X)
        ttk.Label(filt_frame, text="Score:").grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self.score_filter_type = tk.StringVar(value="All")
        score_combo = ttk.Combobox(filt_frame, textvariable=self.score_filter_type, width=12, state="readonly")
        score_combo["values"] = ("All", "Exact %", "Operator", "Label")
        score_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 8))
        self.score_filter_value = ttk.Entry(filt_frame, width=10)
        self.score_filter_value.grid(row=0, column=2, sticky=tk.W, padx=(0, 8))
        ttk.Label(filt_frame, text="(e.g. 75 or >75)").grid(row=0, column=3, sticky=tk.W, padx=(0, 12))
        self.label_filter = tk.StringVar(value=STEAM_LABEL_ORDER[0] if STEAM_LABEL_ORDER else "")
        label_combo = ttk.Combobox(filt_frame, textvariable=self.label_filter, width=22, state="readonly")
        label_combo["values"] = tuple(STEAM_LABEL_ORDER)
        label_combo.grid(row=0, column=4, sticky=tk.W, padx=(0, 8))
        ttk.Label(filt_frame, text="Min reviews:").grid(row=0, column=5, sticky=tk.W, padx=(16, 4))
        self.min_reviews_var = tk.StringVar(value="")
        ttk.Entry(filt_frame, textvariable=self.min_reviews_var, width=8).grid(row=0, column=6, sticky=tk.W, padx=(0, 8))
        ttk.Label(filt_frame, text="% off:").grid(row=0, column=7, sticky=tk.W, padx=(16, 4))
        self.discount_filter_var = tk.StringVar(value="")
        ttk.Entry(filt_frame, textvariable=self.discount_filter_var, width=10).grid(row=0, column=8, sticky=tk.W, padx=(0, 4))
        ttk.Label(filt_frame, text="(e.g. >50)").grid(row=0, column=9, sticky=tk.W, padx=(0, 8))
        ttk.Button(filt_frame, text="Apply filters", command=self._apply_filters_tab2).grid(row=0, column=10, padx=(8, 0))

        # Sale end filter (row 1)
        ttk.Label(filt_frame, text="Sale end:").grid(row=1, column=0, sticky=tk.W, padx=(0, 4), pady=(8, 0))
        self.sale_end_filter_type = tk.StringVar(value="All")
        sale_end_combo = ttk.Combobox(filt_frame, textvariable=self.sale_end_filter_type, width=14, state="readonly")
        sale_end_combo["values"] = ("All", "Ending Soon", "Ending Latest", "By date")
        sale_end_combo.grid(row=1, column=1, sticky=tk.W, padx=(0, 8), pady=(8, 0))
        self.sale_end_filter_value = tk.StringVar(value="")
        ttk.Entry(filt_frame, textvariable=self.sale_end_filter_value, width=28).grid(row=1, column=2, columnspan=2, sticky=tk.W, padx=(0, 4), pady=(8, 0))
        ttk.Label(filt_frame, text="(e.g. <2026-03-01 or 2026-02-01..2026-02-28)").grid(row=1, column=4, columnspan=6, sticky=tk.W, padx=(0, 8), pady=(8, 0))

        ttk.Label(tab2, text="Results (best rating first):").pack(anchor=tk.W, pady=(8, 4))
        self.tab2_sheet_frame = ttk.Frame(tab2)
        self.tab2_sheet_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.tab2_sheet_frame.grid_columnconfigure(0, weight=1)
        self.tab2_sheet_frame.grid_rowconfigure(0, weight=1)
        # Column width ratios (Game, Rating, Reviews, % Off, Release date, Sale end) - sum 1.0
        self._tab2_column_ratios = [0.32, 0.20, 0.12, 0.08, 0.14, 0.14]
        self.tab2_sheet = Sheet(
            self.tab2_sheet_frame,
            headers=["Game", "Rating", "Reviews", "% Off", "Release date", "Sale end"],
            show_row_index=False,
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            height=400,
            default_column_width=80,
            table_wrap="w",
            alternate_color="#F0F4F8",
        )
        # Center text in all columns except Game (column 0)
        self.tab2_sheet.align_columns([1, 2, 3, 4, 5], align="center")
        self.tab2_sheet.enable_bindings()
        self.tab2_sheet.bind("<Double-1>", self._on_tab2_sheet_double_click)
        self.tab2_sheet.grid(row=0, column=0, sticky="nswe")
        self.tab2_sheet_frame.bind("<Configure>", self._resize_tab2_columns)
        self.root.after(100, self._resize_tab2_columns)
        ttk.Label(tab2, text="Double-click a row to open the product page.", font=("TkDefaultFont", 8)).pack(anchor=tk.W)
        copy_btn = ttk.Button(tab2, text="Copy product URLs to clipboard", command=self._copy_tab2_urls)
        copy_btn.pack(anchor=tk.W)

    def _get_selected_currencies(self) -> list[str]:
        return [c for c in ALL_CURRENCIES if self.currency_vars[c].get()]

    def _load_feed(self):
        self.input_text.config(cursor="watch")
        self.root.update()
        try:
            self._feed_items = fetch_and_parse()
            self._index = items_to_index(self._feed_items)
            messagebox.showinfo("Feed loaded", f"Loaded {len(self._feed_items)} variants ({len(self._index)} products).")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load feed:\n{e}")
        finally:
            self.input_text.config(cursor="")

    def _load_feed_tab2(self):
        if self._index is None:
            self._load_feed()
        else:
            messagebox.showinfo("Feed", "Feed already loaded.")

    def _fetch_on_sale(self):
        if self._index is None:
            self._load_feed()
        if self._index is None:
            return
        self.tab2_status.config(text="Getting on-sale products...")
        self.root.update()
        try:
            products = get_on_sale_products(self._index, resolve_steam_by_name=True)
            self.tab2_status.config(text=f"Found {len(products)} on sale. Fetching Steam data...")
            self.root.update()

            def progress(i, total):
                self.tab2_status.config(text=f"Fetching Steam data... {i}/{total}")
                self.root.update()

            self._on_sale_rows = enrich_with_steam_reviews(products, progress_callback=progress)
            self._apply_filters_tab2()
            self.tab2_status.config(text=f"Done. {len(self._tab2_displayed_rows)} products (after filters).")
        except Exception as e:
            messagebox.showerror("Error", f"Failed:\n{e}")
            self.tab2_status.config(text="")
            self._on_sale_rows = []

    def _apply_filters_tab2(self):
        score_type = self.score_filter_type.get()
        score_val = self.score_filter_value.get()
        label_val = self.label_filter.get()
        min_rev = self.min_reviews_var.get()
        discount_val = self.discount_filter_var.get()
        sale_end_type = self.sale_end_filter_type.get()
        sale_end_val = self.sale_end_filter_value.get()
        rows = _apply_score_filter(self._on_sale_rows, score_type, score_val, label_val)
        rows = _apply_reviews_filter(rows, min_rev)
        rows = _apply_discount_filter(rows, discount_val)
        rows = _apply_sale_end_filter(rows, sale_end_type, sale_end_val)
        self._populate_tab2_sheet(rows)

    def _resize_tab2_columns(self, event=None):
        """Distribute column widths across the full table width."""
        try:
            w = self.tab2_sheet_frame.winfo_width()
            if w <= 1:
                return
            scrollbar_w = 20
            total = max(100, w - scrollbar_w)
            widths = [max(40, int(total * r)) for r in self._tab2_column_ratios]
            self.tab2_sheet.set_column_widths(column_widths=widths)
        except (tk.TclError, AttributeError):
            pass

    def _value_to_color(self, t: float) -> str:
        """Map t in [0, 1] to green -> yellow -> orange -> red (hex)."""
        if t <= 0:
            return "#d4edda"
        if t >= 1:
            return "#f8d7da"
        if t < 0.33:
            u = t / 0.33
            return _lerp_hex("#d4edda", "#fff3cd", u)
        if t < 0.66:
            u = (t - 0.33) / 0.33
            return _lerp_hex("#fff3cd", "#ffe5b4", u)
        u = (t - 0.66) / 0.34
        return _lerp_hex("#ffe5b4", "#f8d7da", u)

    def _populate_tab2_sheet(self, rows: list[dict]):
        self._tab2_displayed_rows = rows
        data = []
        for r in rows:
            title = (r.get("title") or "").strip() or "—"
            pct = r.get("steam_percent_positive")
            desc = r.get("steam_review_desc") or ""
            if pct is not None and desc:
                rating = f"{desc} ({pct}%)"
            elif desc:
                rating = desc
            elif pct is not None:
                rating = f"{pct}%"
            else:
                rating = "N/A"
            reviews = r.get("steam_total_reviews")
            reviews_str = str(reviews) if reviews is not None and reviews > 0 else "N/A"
            discount_str = _discount_str(r)
            release_str = _release_date_str(r)
            sale_end_str = _sale_end_str(r)
            data.append([title, rating, reviews_str, discount_str, release_str, sale_end_str])
        self.tab2_sheet.set_sheet_data(data)
        self._apply_tab2_color_scale(rows)
        self._resize_tab2_columns()
        self.tab2_sheet.refresh()

    def _apply_tab2_color_scale(self, rows: list[dict]):
        """Apply green->yellow->orange->red background for Rating (1), Reviews (2), % Off (3)."""
        if not rows:
            return
        n = len(rows)
        # Collect numeric values: col 1 = rating 0-100, col 2 = log10(reviews), col 3 = discount 0-100
        rating_vals = []
        review_vals = []
        discount_vals = []
        for r in rows:
            pct = r.get("steam_percent_positive")
            rating_vals.append(float(pct) if pct is not None else None)
            rev = r.get("steam_total_reviews")
            review_vals.append(math.log10(max(1, rev)) if rev and rev > 0 else None)
            discount_vals.append(float(_discount_pct(r)) if _discount_pct(r) is not None else None)
        for col_idx, vals in enumerate([rating_vals, review_vals, discount_vals]):
            numeric = [v for v in vals if v is not None]
            if not numeric:
                continue
            lo, hi = min(numeric), max(numeric)
            span = hi - lo if hi > lo else 1.0
            sheet_col = col_idx + 1
            for r in range(n):
                v = vals[r]
                if v is None:
                    continue
                t = (v - lo) / span
                color = self._value_to_color(t)
                self.tab2_sheet[(r, sheet_col)].bg = color

    def _on_tab2_sheet_double_click(self, event=None):
        """Open the selected row's product page in the default browser."""
        if not self._tab2_displayed_rows:
            return
        sel = self.tab2_sheet.get_currently_selected()
        if sel is None:
            return
        row_idx = sel.row
        if 0 <= row_idx < len(self._tab2_displayed_rows):
            link = self._tab2_displayed_rows[row_idx].get("link")
            if link:
                webbrowser.open(link)

    def _copy_tab2_urls(self):
        urls = [r.get("link") or "" for r in self._tab2_displayed_rows if r.get("link")]
        if urls:
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(urls))
            messagebox.showinfo("Copied", f"Copied {len(urls)} product URL(s) to clipboard.")
        else:
            messagebox.showwarning("Nothing to copy", "Fetch on-sale list first.")

    def _clear_steam_cache(self):
        clear_steam_cache()
        clear_app_list_cache()
        clear_steam_appdetails_cache()
        messagebox.showinfo("Cache cleared", "Steam review, app list, and appdetails caches cleared.")

    def _build_table(self):
        if self._index is None:
            self._load_feed()
        if self._index is None:
            return
        urls = parse_pasted_urls(self.input_text.get("1.0", tk.END))
        if not urls:
            messagebox.showwarning("No URLs", "Paste at least one product URL.")
            return
        products, not_found = resolve_urls_to_products(self._index, urls)
        currencies = self._get_selected_currencies()
        if not currencies:
            messagebox.showwarning("No currencies", "Select at least one currency.")
            return
        markdown = build_reddit_table(products, currencies)
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, markdown)
        self.output_text.config(state=tk.DISABLED)
        if not_found:
            messagebox.showwarning(
                "Some URLs not found",
                f"{len(not_found)} URL(s) were not found in the feed:\n" + "\n".join(not_found[:5])
                + ("\n..." if len(not_found) > 5 else ""),
            )
        if not products:
            messagebox.showwarning("No products", "No products could be found for the given URLs.")

    def _copy_output(self):
        text = self.output_text.get("1.0", tk.END)
        if text.strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Copied", "Reddit markdown copied to clipboard.")
        else:
            messagebox.showwarning("Nothing to copy", "Build a table first.")

    def run(self):
        self.root.mainloop()


def main():
    app = Application()
    app.run()


if __name__ == "__main__":
    main()
