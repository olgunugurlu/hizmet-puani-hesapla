import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from collections import defaultdict

# -------------------- DAILY POINTS (Madde 21) --------------------
DAILY_POINTS = {
    1: {1: 0.028, 2: 0.031, 3: 0.033, 4: 0.046, 5: 0.053, 6: 0.060},
    2: {1: 0.033, 2: 0.036, 3: 0.039, 4: 0.060, 5: 0.066, 6: 0.073},
    3: {1: 0.039, 2: 0.044, 3: 0.049, 4: 0.073, 5: 0.086, 6: 0.099},
}

# Basit ödül presetleri (tek ve en yüksek mantığına uygun)
COMP_PRESETS = {
    "Yok": 0,
    "TÜBİTAK/TÜBA/Tech - Ulusal 1.lik (1-3 alan)": 15,
    "TÜBİTAK/TÜBA/Tech - Ulusal 2.lik (1-3 alan)": 10,
    "TÜBİTAK/TÜBA/Tech - Ulusal 3.lük/Mansiyon (1-3 alan)": 5,
    "TÜBİTAK/TÜBA/Tech - Uluslararası 1.lik (1-3 alan)": 30,
    "TÜBİTAK/TÜBA/Tech - Uluslararası 2.lik (1-3 alan)": 20,
    "TÜBİTAK/TÜBA/Tech - Uluslararası 3.lük/Mansiyon (1-3 alan)": 10,

    "TÜBİTAK/TÜBA/Tech - Ulusal 1.lik (4-6 alan)": 20,
    "TÜBİTAK/TÜBA/Tech - Ulusal 2.lik (4-6 alan)": 15,
    "TÜBİTAK/TÜBA/Tech - Ulusal 3.lük/Mansiyon (4-6 alan)": 10,
    "TÜBİTAK/TÜBA/Tech - Uluslararası 1.lik (4-6 alan)": 40,
    "TÜBİTAK/TÜBA/Tech - Uluslararası 2.lik (4-6 alan)": 30,
    "TÜBİTAK/TÜBA/Tech - Uluslararası 3.lük/Mansiyon (4-6 alan)": 20,

    "Öğretmen Derece - Ulusal 1.lik": 20,
    "Öğretmen Derece - Ulusal 2.lik": 15,
    "Öğretmen Derece - Ulusal 3.lük/Mansiyon": 10,
    "Öğretmen Derece - Uluslararası 1.lik": 35,
    "Öğretmen Derece - Uluslararası 2.lik": 25,
    "Öğretmen Derece - Uluslararası 3.lük/Mansiyon": 15,
}

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

@dataclass
class TaskRow:
    tab_id: int
    year_var: tk.StringVar
    school_var: tk.StringVar
    region_var: tk.IntVar
    area_var: tk.IntVar
    days_var: tk.StringVar
    daily_lbl: ttk.Label

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hizmet Puanı Hesaplayıcı (Çoklu Okul/Görev - Yıl Bazlı)")
        self.geometry("1050x700")
        self.minsize(1050, 700)

        self.rows: list[TaskRow] = []
        self.next_tab_id = 1

        # Varsayılan: yıl başına hedef iş günü (kurumsal pratik). Yönetmelikte sabit 180 yok.
        self.expected_days_per_year_var = tk.StringVar(value="180")

        # Ek puanlar yıl bazında (tabloya göre)
        self.extra_bel_ybo_var = tk.StringVar(value="0")     # 0.2 each
        self.extra_bel_other_var = tk.StringVar(value="0")   # 0.1 each
        self.extra_dyk_months_var = tk.StringVar(value="0")  # 0.5 per month
        self.extra_telafi_months_var = tk.StringVar(value="0")  # 0.5 per month
        self.extra_zumre_years_var = tk.StringVar(value="0") # 1 per year (max 4 overall)
        self.extra_eba_scenario_var = tk.StringVar(value="0")# 0.2 each
        self.extra_eba_content_var = tk.StringVar(value="0") # 0.3 each
        self.extra_comp_var = tk.StringVar(value="Yok")
        self.extra_manual_var = tk.StringVar(value="0")

        self._build_ui()
        self.add_task_tab()  # start with one tab

    def _build_ui(self):
        pad = 10

        top = ttk.Frame(self)
        top.pack(fill="x", padx=pad, pady=(pad, 6))

        ttk.Label(top, text="Yıl başına hedef iş günü (varsayılan kontrol):").pack(side="left")
        ttk.Entry(top, textvariable=self.expected_days_per_year_var, width=8).pack(side="left", padx=6)
        ttk.Button(top, text="➕ Yeni Görev/Okul", command=self.add_task_tab).pack(side="left", padx=12)
        ttk.Button(top, text="🧮 Hesapla (Yıl Bazlı)", command=self.calculate_all).pack(side="left")

        # Notebook: each tab = a task/assignment record
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=pad, pady=6)

        # Extras frame
        extras = ttk.LabelFrame(self, text="Ek Puanlar (Genel / Yıl Bazında Uygulamak İstersen)")
        extras.pack(fill="x", padx=pad, pady=(6, 6))

        r = 0
        ttk.Label(extras, text="Belletici YBO/Özel Eğitim (0.2/görev):").grid(row=r, column=0, sticky="w", padx=pad, pady=4)
        ttk.Entry(extras, textvariable=self.extra_bel_ybo_var, width=8).grid(row=r, column=1, sticky="w", pady=4)
        ttk.Label(extras, text="Belletici Diğer (0.1/görev):").grid(row=r, column=2, sticky="w", padx=pad, pady=4)
        ttk.Entry(extras, textvariable=self.extra_bel_other_var, width=8).grid(row=r, column=3, sticky="w", pady=4)

        r += 1
        ttk.Label(extras, text="DYK/İYEP (0.5/ay):").grid(row=r, column=0, sticky="w", padx=pad, pady=4)
        ttk.Entry(extras, textvariable=self.extra_dyk_months_var, width=8).grid(row=r, column=1, sticky="w", pady=4)
        ttk.Label(extras, text="Telafi/Destek (0.5/ay):").grid(row=r, column=2, sticky="w", padx=pad, pady=4)
        ttk.Entry(extras, textvariable=self.extra_telafi_months_var, width=8).grid(row=r, column=3, sticky="w", pady=4)

        r += 1
        ttk.Label(extras, text="İl zümre yılı (1/yıl, max 4):").grid(row=r, column=0, sticky="w", padx=pad, pady=4)
        ttk.Entry(extras, textvariable=self.extra_zumre_years_var, width=8).grid(row=r, column=1, sticky="w", pady=4)
        ttk.Label(extras, text="EBA Senaryo (0.2/adet):").grid(row=r, column=2, sticky="w", padx=pad, pady=4)
        ttk.Entry(extras, textvariable=self.extra_eba_scenario_var, width=8).grid(row=r, column=3, sticky="w", pady=4)

        r += 1
        ttk.Label(extras, text="EBA e-İçerik (0.3/adet):").grid(row=r, column=0, sticky="w", padx=pad, pady=4)
        ttk.Entry(extras, textvariable=self.extra_eba_content_var, width=8).grid(row=r, column=1, sticky="w", pady=4)
        ttk.Label(extras, text="Yarışma/Ödül (tek ve en yüksek):").grid(row=r, column=2, sticky="w", padx=pad, pady=4)
        ttk.Combobox(extras, state="readonly", width=42, values=list(COMP_PRESETS.keys()), textvariable=self.extra_comp_var)\
            .grid(row=r, column=3, sticky="w", pady=4)

        r += 1
        ttk.Label(extras, text="Manuel ek puan:").grid(row=r, column=0, sticky="w", padx=pad, pady=4)
        ttk.Entry(extras, textvariable=self.extra_manual_var, width=10).grid(row=r, column=1, sticky="w", pady=4)

        # Results / summary
        bottom = ttk.Frame(self)
        bottom.pack(fill="both", expand=False, padx=pad, pady=(6, pad))

        self.summary = tk.Text(bottom, height=14, wrap="word")
        self.summary.pack(fill="both", expand=True)

    def add_task_tab(self):
        tab_id = self.next_tab_id
        self.next_tab_id += 1

        frame = ttk.Frame(self.nb)
        self.nb.add(frame, text=f"Görev {tab_id}")

        # Default values
        year_var = tk.StringVar(value="2025")
        school_var = tk.StringVar(value=f"Okul/Kurum {tab_id}")
        region_var = tk.IntVar(value=1)
        area_var = tk.IntVar(value=1)
        days_var = tk.StringVar(value="180")

        # Layout
        pad = 12
        ttk.Label(frame, text="Yıl:").grid(row=0, column=0, sticky="w", padx=pad, pady=8)
        ttk.Entry(frame, textvariable=year_var, width=10).grid(row=0, column=1, sticky="w", pady=8)

        ttk.Label(frame, text="Okul / Kurum Adı:").grid(row=0, column=2, sticky="w", padx=pad, pady=8)
        ttk.Entry(frame, textvariable=school_var, width=40).grid(row=0, column=3, sticky="w", pady=8)

        ttk.Label(frame, text="Hizmet Bölgesi:").grid(row=1, column=0, sticky="w", padx=pad, pady=8)
        cb_region = ttk.Combobox(frame, state="readonly", width=8, values=[1, 2, 3], textvariable=region_var)
        cb_region.grid(row=1, column=1, sticky="w", pady=8)

        ttk.Label(frame, text="Hizmet Alanı (1-6):").grid(row=1, column=2, sticky="w", padx=pad, pady=8)
        cb_area = ttk.Combobox(frame, state="readonly", width=8, values=[1,2,3,4,5,6], textvariable=area_var)
        cb_area.grid(row=1, column=3, sticky="w", pady=8)

        ttk.Label(frame, text="Bu kurumda fiilen çalışılan gün (o yıl):").grid(row=2, column=0, sticky="w", padx=pad, pady=8)
        ttk.Entry(frame, textvariable=days_var, width=12).grid(row=2, column=1, sticky="w", pady=8)

        daily_lbl = ttk.Label(frame, text="Günlük puan: -")
        daily_lbl.grid(row=2, column=2, columnspan=2, sticky="w", padx=pad, pady=8)

        # Buttons in tab
        btns = ttk.Frame(frame)
        btns.grid(row=3, column=0, columnspan=4, sticky="w", padx=pad, pady=(10, 8))

        ttk.Button(btns, text="🗑 Bu görevi sil", command=lambda: self.delete_tab(tab_id)).pack(side="left")

        # Update daily label when selections change
        def update_daily(*_):
            reg = region_var.get()
            ar = area_var.get()
            daily = DAILY_POINTS.get(reg, {}).get(ar)
            if daily is None:
                daily_lbl.config(text="Günlük puan: -")
            else:
                daily_lbl.config(text=f"Günlük puan: {daily}  (Bölge {reg} / Alan {ar})")

        cb_region.bind("<<ComboboxSelected>>", update_daily)
        cb_area.bind("<<ComboboxSelected>>", update_daily)
        update_daily()

        self.rows.append(TaskRow(
            tab_id=tab_id,
            year_var=year_var,
            school_var=school_var,
            region_var=region_var,
            area_var=area_var,
            days_var=days_var,
            daily_lbl=daily_lbl
        ))

        self.nb.select(frame)

    def delete_tab(self, tab_id: int):
        # Find index in rows
        idx = None
        for i, r in enumerate(self.rows):
            if r.tab_id == tab_id:
                idx = i
                break
        if idx is None:
            return

        # Remove tab from notebook
        # Tabs are in same order as added; find matching by text "Görev {id}"
        for t in range(len(self.nb.tabs())):
            tab_text = self.nb.tab(t, option="text")
            if tab_text == f"Görev {tab_id}":
                self.nb.forget(t)
                break

        self.rows.pop(idx)

    def calculate_all(self):
        if not self.rows:
            messagebox.showinfo("Bilgi", "En az bir görev kaydı eklemelisiniz.")
            return

        expected = safe_int(self.expected_days_per_year_var.get(), 180)
        if expected <= 0:
            expected = 180

        # Aggregate by year
        by_year_days = defaultdict(int)
        by_year_points = defaultdict(float)
        by_year_lines = defaultdict(list)

        # Validate and compute each row
        for row in self.rows:
            year = row.year_var.get().strip()
            school = row.school_var.get().strip() or f"Görev {row.tab_id}"
            reg = row.region_var.get()
            area = row.area_var.get()
            days = safe_int(row.days_var.get(), -1)

            if not year.isdigit() or len(year) != 4:
                messagebox.showerror("Hata", f"[Görev {row.tab_id}] Yıl 4 haneli olmalı. (Örn: 2025)")
                return
            if days < 0:
                messagebox.showerror("Hata", f"[Görev {row.tab_id}] Gün sayısı geçerli bir sayı olmalı.")
                return

            daily = DAILY_POINTS.get(reg, {}).get(area)
            if daily is None:
                messagebox.showerror("Hata", f"[Görev {row.tab_id}] Bölge/Alan seçimi hatalı.")
                return

            pts = daily * days

            by_year_days[year] += days
            by_year_points[year] += pts
            by_year_lines[year].append(
                f"  - {school} | Bölge {reg}, Alan {area} | Gün: {days} | Günlük: {daily} | Puan: {pts:.3f}"
            )

        # Extras (global) - istersen bunu yıl bazına da genişletiriz
        bel_ybo = safe_int(self.extra_bel_ybo_var.get())
        bel_other = safe_int(self.extra_bel_other_var.get())
        bel_points = bel_ybo * 0.2 + bel_other * 0.1

        dyk_m = safe_int(self.extra_dyk_months_var.get())
        tel_m = safe_int(self.extra_telafi_months_var.get())
        dyk_points = dyk_m * 0.5
        tel_points = tel_m * 0.5

        zumre_y = safe_int(self.extra_zumre_years_var.get())
        if zumre_y > 4:
            zumre_y = 4
        zumre_points = zumre_y * 1.0

        eba_s = safe_int(self.extra_eba_scenario_var.get())
        eba_c = safe_int(self.extra_eba_content_var.get())
        eba_points = eba_s * 0.2 + eba_c * 0.3

        comp_points = COMP_PRESETS.get(self.extra_comp_var.get(), 0)
        manual_extra = safe_float(self.extra_manual_var.get(), 0.0)

        extra_total = bel_points + dyk_points + tel_points + zumre_points + eba_points + comp_points + manual_extra

        # Compose summary
        years_sorted = sorted(by_year_days.keys())
        grand_base = sum(by_year_points.values())
        grand_total = grand_base + extra_total

        out = []
        out.append("HİZMET PUANI HESAP ÖZETİ (Yıl Bazlı / Çoklu Okul-Görev)\n")
        out.append(f"Yıl başına hedef iş günü (kontrol): {expected}\n")

        for y in years_sorted:
            out.append(f"== {y} ==")
            out.append(f"Toplam gün: {by_year_days[y]}   |   Temel puan: {by_year_points[y]:.3f}")
            if by_year_days[y] != expected:
                out.append(f"⚠ UYARI: {y} yılı toplam gün {by_year_days[y]} (hedef {expected}). "
                           f"Bu, görevlendirme/izin/sigorta günü vb. durumlara göre normal olabilir; kontrol edin.")
            out.append("Detaylar:")
            out.extend(by_year_lines[y])
            out.append("")

        out.append("== EK PUANLAR (Genel) ==")
        out.append(f"Belletici: {bel_points:.3f}  (0.2×{bel_ybo} + 0.1×{bel_other})")
        out.append(f"DYK/İYEP: {dyk_points:.3f}  (0.5×{dyk_m} ay)")
        out.append(f"Telafi/Destek: {tel_points:.3f}  (0.5×{tel_m} ay)")
        out.append(f"İl zümre: {zumre_points:.3f}  ({zumre_y} yıl, max 4)")
        out.append(f"EBA: {eba_points:.3f}  (Senaryo 0.2×{eba_s} + İçerik 0.3×{eba_c})")
        out.append(f"Yarışma/Ödül: {comp_points:.3f}  ({self.extra_comp_var.get()})")
        out.append(f"Manuel ek: {manual_extra:.3f}")
        out.append(f"Ek puanlar toplam: {extra_total:.3f}\n")

        out.append(f"GENEL TOPLAM (Temel + Ek): {grand_total:.3f}")
        out.append(f"Temel toplam: {grand_base:.3f}")

        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", "\n".join(out))


if __name__ == "__main__":
    # Windows DPI fix (opsiyonel)
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    app = App()
    app.mainloop()
