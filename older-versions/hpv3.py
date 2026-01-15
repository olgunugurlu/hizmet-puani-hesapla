import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from collections import defaultdict

# -------------------- DAILY POINTS TABLE (Madde 21 günlük puan) --------------------
DAILY_POINTS = {
    1: {1: 0.028, 2: 0.031, 3: 0.033, 4: 0.046, 5: 0.053, 6: 0.060},
    2: {1: 0.033, 2: 0.036, 3: 0.039, 4: 0.060, 5: 0.066, 6: 0.073},
    3: {1: 0.039, 2: 0.044, 3: 0.049, 4: 0.073, 5: 0.086, 6: 0.099},
}

# -------------------- HELPERS --------------------
def safe_int(x: str, default=0) -> int:
    try:
        return int(str(x).strip())
    except:
        return default

def safe_float(x: str, default=0.0) -> float:
    try:
        return float(str(x).strip().replace(",", "."))
    except:
        return default

def parse_iso(d: str) -> date:
    return datetime.strptime(d.strip(), "%Y-%m-%d").date()

def daterange_inclusive(start: date, end: date):
    if end < start:
        start, end = end, start
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)

# -------------------- CALENDAR RULES (İş takvimi formu) --------------------
KIND_LABELS = {
    "OFF_FULL": "İş günü sayılmayan (tam gün)",
    "OFF_HALF": "İş günü sayılmayan (yarım gün)",
    "COUNT_AS_WORKDAY": "İş günü sayılır (tören vb.)",
}

@dataclass
class CalendarRange:
    start: date
    end: date
    kind: str
    note: str = ""

class WorkCalendar:
    def __init__(self):
        self.ranges: list[CalendarRange] = []

    def add_range(self, r: CalendarRange):
        self.ranges.append(r)

    def remove_index(self, idx: int):
        if 0 <= idx < len(self.ranges):
            self.ranges.pop(idx)

    def expand_effects(self):
        # Priority: COUNT_AS_WORKDAY > OFF_FULL > OFF_HALF
        off_full, off_half, force_work = set(), set(), set()
        for r in self.ranges:
            for d in daterange_inclusive(r.start, r.end):
                if r.kind == "COUNT_AS_WORKDAY":
                    force_work.add(d)
                elif r.kind == "OFF_FULL":
                    off_full.add(d)
                elif r.kind == "OFF_HALF":
                    off_half.add(d)

        off_full -= force_work
        off_half -= force_work
        off_half -= off_full
        return off_full, off_half, force_work

    def business_days_between(self, start: date, end: date):
        off_full, off_half, force_work = self.expand_effects()
        work = 0.0
        for d in daterange_inclusive(start, end):
            if d.weekday() >= 5:
                continue
            if d in force_work:
                work += 1.0
                continue
            if d in off_full:
                continue
            if d in off_half:
                work += 0.5
                continue
            work += 1.0
        return work

# -------------------- EXTRA POINTS (Yönetmelik ek puanlar) --------------------
# Öğrenci çalıştırma yarışmaları (TÜBİTAK/TÜBA/teknoloji) – hizmet alanı grubuna göre
STUDENT_AWARD_POINTS = {
    "Ulusal 1.": {"1-3": 15, "4-6": 20},
    "Ulusal 2.": {"1-3": 10, "4-6": 15},
    "Ulusal 3./Mansiyon": {"1-3": 5, "4-6": 10},
    "Uluslararası 1.": {"1-3": 30, "4-6": 40},
    "Uluslararası 2.": {"1-3": 20, "4-6": 30},
    "Uluslararası 3./Mansiyon": {"1-3": 10, "4-6": 20},
    "Yok": {"1-3": 0, "4-6": 0},
}

# Öğretmenin kendi yarışma derecesi (bilimsel/sanatsal/sportif)
TEACHER_AWARD_POINTS = {
    "Ulusal 1.": 20,
    "Ulusal 2.": 15,
    "Ulusal 3./Mansiyon": 10,
    "Uluslararası 1.": 35,
    "Uluslararası 2.": 25,
    "Uluslararası 3./Mansiyon": 15,
    "Yok": 0,
}

# -------------------- UI MODEL --------------------
@dataclass
class TaskRow:
    tab_id: int
    frame: ttk.Frame
    year_var: tk.StringVar
    school_var: tk.StringVar
    region_var: tk.IntVar
    area_var: tk.IntVar
    mode_var: tk.StringVar  # "days" or "range"
    days_var: tk.StringVar
    start_var: tk.StringVar
    end_var: tk.StringVar
    daily_lbl: ttk.Label
    computed_lbl: ttk.Label

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hizmet Puanı (Takvim + Temel + Ek Puanlar / Yönetmelik Uyumlu)")
        self.geometry("1320x860")
        self.minsize(1320, 860)

        self.rows: list[TaskRow] = []
        self.next_tab_id = 1

        self.expected_days_per_year_var = tk.StringVar(value="180")

        # Work calendar (editable)
        self.calendar = WorkCalendar()

        # Extra points vars
        self.bel_ybo_var = tk.StringVar(value="0")       # 0.2 / görev
        self.bel_other_var = tk.StringVar(value="0")     # 0.1 / görev

        self.dyk_months_var = tk.StringVar(value="0")    # 0.5 / ay
        self.telafi_months_var = tk.StringVar(value="0") # 0.5 / ay (ayda çok eğitim olsa bile tek sayılır)

        self.student_award_var = tk.StringVar(value="Yok")  # TÜBİTAK vb.
        self.student_award_area_group_var = tk.StringVar(value="1-3")  # 1-3 veya 4-6

        self.teacher_award_var = tk.StringVar(value="Yok")  # öğretmenin kendi derecesi

        # EBA / İÇYS (takvim yılı max 10)
        self.eba_scenario_var = tk.StringVar(value="0")  # 0.2/adet
        self.eba_content_var = tk.StringVar(value="0")   # 0.3/adet
        self.eba_ministry_assignment_var = tk.BooleanVar(value=False)

        # İl zümre (max 4)
        self.zumre_years_var = tk.StringVar(value="0")

        # Manual
        self.manual_extra_var = tk.StringVar(value="0")

        self._build_ui()
        self._load_default_calendar_2025_2026()
        self._refresh_calendar_list()
        self.add_task_tab()

    # ---------------- UI BUILD ----------------
    def _build_ui(self):
        pad = 10

        top = ttk.Frame(self)
        top.pack(fill="x", padx=pad, pady=(pad, 6))

        ttk.Label(top, text="Yıl başına hedef iş günü (kontrol):").pack(side="left")
        ttk.Entry(top, textvariable=self.expected_days_per_year_var, width=8).pack(side="left", padx=6)

        ttk.Button(top, text="➕ Yeni Görev/Okul", command=self.add_task_tab).pack(side="left", padx=10)
        ttk.Button(top, text="🧮 Hesapla (Temel + Ek)", command=self.calculate_all).pack(side="left", padx=6)

        self.main_nb = ttk.Notebook(self)
        self.main_nb.pack(fill="both", expand=True, padx=pad, pady=6)

        # Tasks tab
        self.tab_tasks = ttk.Frame(self.main_nb)
        self.main_nb.add(self.tab_tasks, text="Görevler (Temel Puan)")
        self.tasks_nb = ttk.Notebook(self.tab_tasks)
        self.tasks_nb.pack(fill="both", expand=True, padx=pad, pady=pad)

        # Calendar tab
        self.tab_calendar = ttk.Frame(self.main_nb)
        self.main_nb.add(self.tab_calendar, text="Takvim / Tatiller (İş Günü)")
        self._build_calendar_tab()

        # Extras tab
        self.tab_extras = ttk.Frame(self.main_nb)
        self.main_nb.add(self.tab_extras, text="Ek Puanlar (Yönetmelik)")
        self._build_extras_tab()

        # Summary
        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=False, padx=pad, pady=(6, pad))
        self.summary = tk.Text(bottom, height=16, wrap="word")
        self.summary.pack(fill="both", expand=True)

    def _build_calendar_tab(self):
        pad = 12

        info = ttk.LabelFrame(self.tab_calendar, text="Takvim Mantığı")
        info.pack(fill="x", padx=pad, pady=(pad, 6))
        ttk.Label(
            info,
            text=(
                "• Hafta sonları otomatik düşülür.\n"
                "• Aşağıdaki aralıklar iş günü hesabını etkiler:\n"
                "   - İş günü sayılmayan (tam gün): hafta içiyse 1 gün düşer\n"
                "   - İş günü sayılmayan (yarım gün): hafta içiyse 0.5 gün düşer\n"
                "   - İş günü sayılır (tören vb.): varsa diğer tatil kurallarını ezer (1 gün sayar)\n"
                "• 29 Ekim/23 Nisan/19 Mayıs gibi tören günleri iş günü sayılabilir."
            ),
            justify="left"
        ).pack(anchor="w", padx=pad, pady=8)

        form = ttk.LabelFrame(self.tab_calendar, text="Tatil / İstisna Aralığı Ekle")
        form.pack(fill="x", padx=pad, pady=6)

        self.cal_start_var = tk.StringVar(value="2025-11-10")
        self.cal_end_var = tk.StringVar(value="2025-11-14")
        self.cal_kind_var = tk.StringVar(value="OFF_FULL")
        self.cal_note_var = tk.StringVar(value="Ara tatil")

        ttk.Label(form, text="Başlangıç (YYYY-MM-DD):").grid(row=0, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(form, textvariable=self.cal_start_var, width=14).grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(form, text="Bitiş (YYYY-MM-DD):").grid(row=0, column=2, sticky="w", padx=pad, pady=6)
        ttk.Entry(form, textvariable=self.cal_end_var, width=14).grid(row=0, column=3, sticky="w", pady=6)

        ttk.Label(form, text="Tür:").grid(row=1, column=0, sticky="w", padx=pad, pady=6)
        kind_cb = ttk.Combobox(
            form, state="readonly", width=40,
            values=[f"{k} — {v}" for k, v in KIND_LABELS.items()],
        )
        kind_cb.grid(row=1, column=1, columnspan=2, sticky="w", pady=6)
        kind_cb.current(0)

        def on_kind_change(_):
            sel = kind_cb.get().split(" — ")[0].strip()
            self.cal_kind_var.set(sel)

        kind_cb.bind("<<ComboboxSelected>>", on_kind_change)
        on_kind_change(None)

        ttk.Label(form, text="Açıklama:").grid(row=1, column=3, sticky="w", padx=pad, pady=6)
        ttk.Entry(form, textvariable=self.cal_note_var, width=34).grid(row=1, column=4, sticky="w", pady=6)

        ttk.Button(form, text="➕ Ekle", command=self._calendar_add).grid(row=0, column=4, sticky="w", padx=pad, pady=6)

        lst = ttk.LabelFrame(self.tab_calendar, text="Tanımlı Tatiller / İstisnalar")
        lst.pack(fill="both", expand=True, padx=pad, pady=(6, pad))

        self.calendar_list = tk.Listbox(lst, height=16)
        self.calendar_list.pack(fill="both", expand=True, padx=pad, pady=pad)

        btns = ttk.Frame(lst)
        btns.pack(fill="x", padx=pad, pady=(0, pad))
        ttk.Button(btns, text="🗑 Seçiliyi Sil", command=self._calendar_delete_selected).pack(side="left")
        ttk.Button(btns, text="↺ Varsayılan 2025–2026 Takvimini Yeniden Yükle", command=self._reset_default_calendar).pack(side="left", padx=10)

    def _build_extras_tab(self):
        pad = 12

        box = ttk.LabelFrame(self.tab_extras, text="Ek Puan Girişleri (Yönetmelik kuralları + limitler uygulanır)")
        box.pack(fill="x", padx=pad, pady=(pad, 6))

        r = 0
        ttk.Label(box, text="Nöbetçi belletici YBO/Özel Eğitim pansiyonu (0,2 / görev):").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(box, textvariable=self.bel_ybo_var, width=10).grid(row=r, column=1, sticky="w", pady=6)
        ttk.Label(box, text="Diğer pansiyon (0,1 / görev):").grid(row=r, column=2, sticky="w", padx=pad, pady=6)
        ttk.Entry(box, textvariable=self.bel_other_var, width=10).grid(row=r, column=3, sticky="w", pady=6)

        r += 1
        ttk.Label(box, text="DYK/İYEP görev ayı (0,5 / ay):").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(box, textvariable=self.dyk_months_var, width=10).grid(row=r, column=1, sticky="w", pady=6)
        ttk.Label(box, text="Telafi/Destek ayı (0,5 / ay) (ayda çok eğitim olsa bile tek sayılır):").grid(row=r, column=2, sticky="w", padx=pad, pady=6)
        ttk.Entry(box, textvariable=self.telafi_months_var, width=10).grid(row=r, column=3, sticky="w", pady=6)

        r += 1
        ttk.Label(box, text="TÜBİTAK/TÜBA/teknoloji (öğrenci çalıştırma) – sadece 1 defa en yüksek:").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Combobox(box, state="readonly", width=22, values=list(STUDENT_AWARD_POINTS.keys()), textvariable=self.student_award_var)\
            .grid(row=r, column=1, sticky="w", pady=6)
        ttk.Label(box, text="Hizmet alanı grubun:").grid(row=r, column=2, sticky="w", padx=pad, pady=6)
        ttk.Combobox(box, state="readonly", width=10, values=["1-3", "4-6"], textvariable=self.student_award_area_group_var)\
            .grid(row=r, column=3, sticky="w", pady=6)

        r += 1
        ttk.Label(box, text="Öğretmenin kendi yarışma derecesi – sadece biri ve en yüksek:").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Combobox(box, state="readonly", width=22, values=list(TEACHER_AWARD_POINTS.keys()), textvariable=self.teacher_award_var)\
            .grid(row=r, column=1, sticky="w", pady=6)

        r += 1
        ttk.Label(box, text="EBA/İÇYS Senaryo→e-içerik (0,2/adet) (takvim yılı max 10):").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(box, textvariable=self.eba_scenario_var, width=10).grid(row=r, column=1, sticky="w", pady=6)
        ttk.Label(box, text="EBA/İÇYS e-içerik üretimi (0,3/adet) (takvim yılı max 10):").grid(row=r, column=2, sticky="w", padx=pad, pady=6)
        ttk.Entry(box, textvariable=self.eba_content_var, width=10).grid(row=r, column=3, sticky="w", pady=6)

        r += 1
        ttk.Checkbutton(
            box,
            text="Bakanlık merkez/taşra teşkilatına e-içerik üretmek için görevlendirildim (bu fıkra kapsamında PUAN YOK)",
            variable=self.eba_ministry_assignment_var
        ).grid(row=r, column=0, columnspan=4, sticky="w", padx=pad, pady=6)

        r += 1
        ttk.Label(box, text="İl zümre başkanlığı yılı (1/yıl, toplam max 4):").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(box, textvariable=self.zumre_years_var, width=10).grid(row=r, column=1, sticky="w", pady=6)

        r += 1
        ttk.Label(box, text="Manuel ek puan (isteğe bağlı):").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(box, textvariable=self.manual_extra_var, width=10).grid(row=r, column=1, sticky="w", pady=6)

    # ---------------- Default calendar (from your iş-takvimi) ----------------
    def _load_default_calendar_2025_2026(self):
        self.calendar.ranges.clear()
        # Ara tatil
        self.calendar.add_range(CalendarRange(parse_iso("2025-11-10"), parse_iso("2025-11-14"), "OFF_FULL", "Ara tatil"))
        # Yarıyıl
        self.calendar.add_range(CalendarRange(parse_iso("2026-01-19"), parse_iso("2026-01-30"), "OFF_FULL", "Yarıyıl tatili"))
        # Ara tatil
        self.calendar.add_range(CalendarRange(parse_iso("2026-03-16"), parse_iso("2026-03-20"), "OFF_FULL", "Ara tatil"))
        # Ramazan Bayramı (PDF: 19-22 Mart 2026, 3.5 gün; burada tam gün aralığı olarak girildi)
        self.calendar.add_range(CalendarRange(parse_iso("2026-03-19"), parse_iso("2026-03-22"), "OFF_FULL", "Ramazan Bayramı (istersen 19 Mart'ı yarım gün yap)"))
        # Kurban Bayramı (26-30 Mayıs 2026)
        self.calendar.add_range(CalendarRange(parse_iso("2026-05-26"), parse_iso("2026-05-30"), "OFF_FULL", "Kurban Bayramı"))
        # Tören günleri iş günü sayılır
        self.calendar.add_range(CalendarRange(parse_iso("2025-10-29"), parse_iso("2025-10-29"), "COUNT_AS_WORKDAY", "29 Ekim tören (iş günü sayılır)"))
        self.calendar.add_range(CalendarRange(parse_iso("2026-04-23"), parse_iso("2026-04-23"), "COUNT_AS_WORKDAY", "23 Nisan tören (iş günü sayılır)"))
        self.calendar.add_range(CalendarRange(parse_iso("2026-05-19"), parse_iso("2026-05-19"), "COUNT_AS_WORKDAY", "19 Mayıs tören (iş günü sayılır)"))

    def _reset_default_calendar(self):
        self._load_default_calendar_2025_2026()
        self._refresh_calendar_list()
        messagebox.showinfo("Bilgi", "Varsayılan 2025–2026 takvimi yeniden yüklendi.")

    def _calendar_add(self):
        try:
            s = parse_iso(self.cal_start_var.get())
            e = parse_iso(self.cal_end_var.get())
        except Exception:
            messagebox.showerror("Hata", "Tarih formatı YYYY-MM-DD olmalı.")
            return
        kind = self.cal_kind_var.get().strip()
        if kind not in KIND_LABELS:
            messagebox.showerror("Hata", "Geçersiz tür.")
            return
        note = self.cal_note_var.get().strip()
        self.calendar.add_range(CalendarRange(s, e, kind, note))
        self._refresh_calendar_list()

    def _calendar_delete_selected(self):
        sel = self.calendar_list.curselection()
        if not sel:
            return
        self.calendar.remove_index(sel[0])
        self._refresh_calendar_list()

    def _refresh_calendar_list(self):
        self.calendar_list.delete(0, "end")
        for r in self.calendar.ranges:
            self.calendar_list.insert(
                "end",
                f"{r.start.isoformat()} → {r.end.isoformat()} | {KIND_LABELS.get(r.kind, r.kind)} | {r.note}"
            )

    # ---------------- Tasks ----------------
    def add_task_tab(self):
        tab_id = self.next_tab_id
        self.next_tab_id += 1

        frame = ttk.Frame(self.tasks_nb)
        self.tasks_nb.add(frame, text=f"Görev {tab_id}")

        year_var = tk.StringVar(value="2025")
        school_var = tk.StringVar(value=f"Okul/Kurum {tab_id}")
        region_var = tk.IntVar(value=1)
        area_var = tk.IntVar(value=1)

        mode_var = tk.StringVar(value="range")
        days_var = tk.StringVar(value="")
        start_var = tk.StringVar(value="2025-09-08")
        end_var = tk.StringVar(value="2026-06-26")

        pad = 12
        ttk.Label(frame, text="Yıl (rapor gruplaması için):").grid(row=0, column=0, sticky="w", padx=pad, pady=8)
        ttk.Entry(frame, textvariable=year_var, width=10).grid(row=0, column=1, sticky="w", pady=8)

        ttk.Label(frame, text="Okul / Kurum:").grid(row=0, column=2, sticky="w", padx=pad, pady=8)
        ttk.Entry(frame, textvariable=school_var, width=52).grid(row=0, column=3, sticky="w", pady=8)

        ttk.Label(frame, text="Hizmet Bölgesi:").grid(row=1, column=0, sticky="w", padx=pad, pady=8)
        cb_region = ttk.Combobox(frame, state="readonly", width=8, values=[1, 2, 3], textvariable=region_var)
        cb_region.grid(row=1, column=1, sticky="w", pady=8)

        ttk.Label(frame, text="Hizmet Alanı (1-6):").grid(row=1, column=2, sticky="w", padx=pad, pady=8)
        cb_area = ttk.Combobox(frame, state="readonly", width=8, values=[1,2,3,4,5,6], textvariable=area_var)
        cb_area.grid(row=1, column=3, sticky="w", pady=8)

        daily_lbl = ttk.Label(frame, text="Günlük puan: -")
        daily_lbl.grid(row=2, column=0, columnspan=4, sticky="w", padx=pad, pady=(2, 8))

        box = ttk.LabelFrame(frame, text="Fiili süre girişi")
        box.grid(row=3, column=0, columnspan=4, sticky="ew", padx=pad, pady=8)

        ttk.Radiobutton(box, text="Gün gir", value="days", variable=mode_var).grid(row=0, column=0, sticky="w", padx=10, pady=6)
        ttk.Label(box, text="İş günü:").grid(row=0, column=1, sticky="w", padx=10, pady=6)
        ttk.Entry(box, textvariable=days_var, width=12).grid(row=0, column=2, sticky="w", pady=6)

        ttk.Radiobutton(box, text="Tarih aralığı gir (takvime göre iş günü hesapla)", value="range", variable=mode_var).grid(row=1, column=0, sticky="w", padx=10, pady=6)
        ttk.Label(box, text="Başlangıç:").grid(row=1, column=1, sticky="w", padx=10, pady=6)
        ttk.Entry(box, textvariable=start_var, width=14).grid(row=1, column=2, sticky="w", pady=6)
        ttk.Label(box, text="Bitiş:").grid(row=1, column=3, sticky="w", padx=10, pady=6)
        ttk.Entry(box, textvariable=end_var, width=14).grid(row=1, column=4, sticky="w", pady=6)

        computed_lbl = ttk.Label(box, text="Hesaplanan iş günü: -")
        computed_lbl.grid(row=2, column=1, columnspan=4, sticky="w", padx=10, pady=(0, 6))

        ttk.Button(
            box,
            text="📅 İş gününü hesapla",
            command=lambda: self._compute_days_into_entry(tab_id)
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 6))

        btns = ttk.Frame(frame)
        btns.grid(row=4, column=0, columnspan=4, sticky="w", padx=pad, pady=(6, 10))
        ttk.Button(btns, text="🗑 Bu görevi sil", command=lambda: self.delete_task_tab(tab_id)).pack(side="left")

        def update_daily(*_):
            reg = region_var.get()
            ar = area_var.get()
            daily = DAILY_POINTS.get(reg, {}).get(ar)
            daily_lbl.config(text=f"Günlük puan: {daily} (Bölge {reg} / Alan {ar})" if daily else "Günlük puan: -")

        cb_region.bind("<<ComboboxSelected>>", update_daily)
        cb_area.bind("<<ComboboxSelected>>", update_daily)
        update_daily()

        self.rows.append(TaskRow(
            tab_id=tab_id, frame=frame,
            year_var=year_var, school_var=school_var,
            region_var=region_var, area_var=area_var,
            mode_var=mode_var, days_var=days_var,
            start_var=start_var, end_var=end_var,
            daily_lbl=daily_lbl, computed_lbl=computed_lbl
        ))

        self.tasks_nb.select(frame)

    def delete_task_tab(self, tab_id: int):
        for t in range(len(self.tasks_nb.tabs())):
            if self.tasks_nb.tab(t, option="text") == f"Görev {tab_id}":
                self.tasks_nb.forget(t)
                break
        self.rows = [r for r in self.rows if r.tab_id != tab_id]

    def _get_row(self, tab_id: int):
        for r in self.rows:
            if r.tab_id == tab_id:
                return r
        return None

    def _compute_days_into_entry(self, tab_id: int):
        row = self._get_row(tab_id)
        if not row:
            return
        try:
            s = parse_iso(row.start_var.get())
            e = parse_iso(row.end_var.get())
        except Exception:
            messagebox.showerror("Hata", f"[Görev {tab_id}] Tarih formatı YYYY-MM-DD olmalı.")
            return

        work = self.calendar.business_days_between(s, e)
        row.days_var.set(str(int(work)) if float(work).is_integer() else str(work))
        row.mode_var.set("range")
        row.computed_lbl.config(text=f"Hesaplanan iş günü: {work} (Takvim kuralları uygulandı)")

    # ---------------- Calculation: Base + Extra ----------------
    def calculate_all(self):
        if not self.rows:
            messagebox.showinfo("Bilgi", "En az bir görev kaydı ekleyin.")
            return

        expected = safe_int(self.expected_days_per_year_var.get(), 180)
        if expected <= 0:
            expected = 180

        # --- Base (temel) ---
        by_year_days = defaultdict(float)
        by_year_points = defaultdict(float)
        by_year_lines = defaultdict(list)

        for row in self.rows:
            year = row.year_var.get().strip()
            school = row.school_var.get().strip() or f"Görev {row.tab_id}"
            reg = row.region_var.get()
            area = row.area_var.get()

            if not year.isdigit() or len(year) != 4:
                messagebox.showerror("Hata", f"[Görev {row.tab_id}] Yıl 4 haneli olmalı (Örn 2025).")
                return

            if row.mode_var.get() == "range":
                try:
                    s = parse_iso(row.start_var.get())
                    e = parse_iso(row.end_var.get())
                except Exception:
                    messagebox.showerror("Hata", f"[Görev {row.tab_id}] Tarih formatı YYYY-MM-DD olmalı.")
                    return
                days = self.calendar.business_days_between(s, e)
                row.days_var.set(str(int(days)) if float(days).is_integer() else str(days))
                row.computed_lbl.config(text=f"Hesaplanan iş günü: {days} (Takvim kuralları uygulandı)")
            else:
                days = safe_float(row.days_var.get(), -1.0)

            if days < 0:
                messagebox.showerror("Hata", f"[Görev {row.tab_id}] Gün sayısı geçerli olmalı.")
                return

            daily = DAILY_POINTS.get(reg, {}).get(area)
            if daily is None:
                messagebox.showerror("Hata", f"[Görev {row.tab_id}] Bölge/Alan seçimi hatalı.")
                return

            pts = daily * days
            by_year_days[year] += days
            by_year_points[year] += pts
            by_year_lines[year].append(
                f"  - {school} | Bölge {reg}, Alan {area} | İş günü: {days} | Günlük: {daily} | Temel Puan: {pts:.3f}"
            )

        base_total = sum(by_year_points.values())

        # --- Extras (yönetmelik ek puanları) ---
        warnings = []

        # Belletici: 0.2 / 0.1
        bel_ybo = safe_int(self.bel_ybo_var.get(), 0)
        bel_other = safe_int(self.bel_other_var.get(), 0)
        bel_points = bel_ybo * 0.2 + bel_other * 0.1

        # DYK/İYEP: 0.5 / ay
        dyk_m = safe_int(self.dyk_months_var.get(), 0)
        dyk_points = dyk_m * 0.5

        # Telafi/destek: 0.5 / ay (ay içinde çok eğitim olsa da 1 eğitim sayılır)
        tel_m = safe_int(self.telafi_months_var.get(), 0)
        tel_points = tel_m * 0.5
        if tel_m > 0:
            warnings.append("Telafi/Destek: Ay içinde birden fazla eğitim olsa bile yalnızca bir eğitim esas alınır; giriş ay sayısıdır. (0,5/ay)")

        # Öğrenci çalıştırma yarışması: bir defa en yüksek
        st_sel = self.student_award_var.get()
        st_group = self.student_award_area_group_var.get()
        student_points = STUDENT_AWARD_POINTS.get(st_sel, {"1-3": 0, "4-6": 0}).get(st_group, 0)
        if st_sel != "Yok":
            warnings.append("Öğrenci yarışması puanı: Yönetmeliğe göre yalnızca bir defa ve duruma uygun en yüksek puan verilir (tek seçim uygulanmıştır).")

        # Öğretmenin kendi derecesi: sadece biri ve en yüksek
        t_sel = self.teacher_award_var.get()
        teacher_points = TEACHER_AWARD_POINTS.get(t_sel, 0)
        if t_sel != "Yok":
            warnings.append("Öğretmen yarışma puanı: Yönetmeliğe göre sadece biri ve en yüksek puan esas alınır (tek seçim uygulanmıştır).")

        # EBA/İÇYS: takvim yılı içinde 10'u geçemez; görevlendirme varsa puan yok
        eba_s = safe_int(self.eba_scenario_var.get(), 0)
        eba_c = safe_int(self.eba_content_var.get(), 0)

        eba_s_cap = min(eba_s, 10)
        eba_c_cap = min(eba_c, 10)
        if eba_s > 10 or eba_c > 10:
            warnings.append("EBA/İÇYS: Takvim yılı içinde sayı 10’u geçemez; hesaplamada 10 ile sınırlandı.")

        if self.eba_ministry_assignment_var.get():
            eba_points = 0.0
            if eba_s_cap > 0 or eba_c_cap > 0:
                warnings.append("EBA/İÇYS: Bakanlık merkez/taşra teşkilatına e-içerik üretmek için görevlendirilenlere bu fıkra kapsamında puan verilmez; EBA puanı 0 alındı.")
        else:
            eba_points = eba_s_cap * 0.2 + eba_c_cap * 0.3

        # İl zümre: 1/yıl, max 4
        zumre_y = safe_int(self.zumre_years_var.get(), 0)
        if zumre_y > 4:
            warnings.append("İl zümre: Toplam en fazla 4 puan verilir; hesaplamada 4 ile sınırlandı.")
            zumre_y = 4
        zumre_points = zumre_y * 1.0

        # Manual
        manual_points = safe_float(self.manual_extra_var.get(), 0.0)

        extras_total = bel_points + dyk_points + tel_points + student_points + teacher_points + eba_points + zumre_points + manual_points
        grand_total = base_total + extras_total

        # Yönetmelik notu (GM teklifi): raporda uyarı
        if st_sel != "Yok" or (not self.eba_ministry_assignment_var.get() and (eba_s_cap > 0 or eba_c_cap > 0)):
            warnings.append("Not: Yarışma (5. fıkra) ve EBA/İÇYS (8. fıkra) kapsamındaki puanlar ilgili genel müdürlüğün teklifi üzerine verilir.")

        # --- Output ---
        years_sorted = sorted(by_year_days.keys())
        out = []
        out.append("HİZMET PUANI HESAP ÖZETİ (Temel + Ek Puanlar)\n")
        out.append(f"Yıl başına hedef iş günü (kontrol): {expected}\n")

        for y in years_sorted:
            out.append(f"== {y} ==")
            out.append(f"Toplam iş günü: {by_year_days[y]} | Temel puan: {by_year_points[y]:.3f}")
            if abs(by_year_days[y] - expected) > 0.01:
                out.append(f"⚠ UYARI: {y} iş günü {by_year_days[y]} (kontrol hedefi {expected}). Takvim/görevlendirme farkı olabilir.")
            out.append("Detaylar:")
            out.extend(by_year_lines[y])
            out.append("")

        out.append("== EK PUANLAR ==")
        out.append(f"Nöbetçi belletici: {bel_points:.3f}  (0,2×{bel_ybo} + 0,1×{bel_other})")
        out.append(f"DYK/İYEP: {dyk_points:.3f}  (0,5×{dyk_m} ay)")
        out.append(f"Telafi/Destek: {tel_points:.3f}  (0,5×{tel_m} ay)")
        out.append(f"Öğrenci yarışması (TÜBİTAK/TÜBA/Tech): {student_points:.3f}  ({st_sel}, grup {st_group})")
        out.append(f"Öğretmen derecesi (ulusal/uluslararası): {teacher_points:.3f}  ({t_sel})")
        out.append(f"EBA/İÇYS: {eba_points:.3f}  (Senaryo 0,2×{eba_s_cap} + İçerik 0,3×{eba_c_cap})")
        out.append(f"İl zümre: {zumre_points:.3f}  ({zumre_y} yıl, max 4)")
        out.append(f"Manuel ek: {manual_points:.3f}")
        out.append(f"Ek puan toplamı: {extras_total:.3f}\n")

        if warnings:
            out.append("== KRİTER / UYARI ==")
            for w in warnings:
                out.append(f"⚠ {w}")
            out.append("")

        out.append(f"TEMEL TOPLAM: {base_total:.3f}")
        out.append(f"GENEL TOPLAM (Temel + Ek): {grand_total:.3f}")

        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", "\n".join(out))

        if warnings:
            messagebox.showwarning("Kriter / Uyarı", "\n".join(warnings))


if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    App().mainloop()
