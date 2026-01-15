import tkinter as tk
from tkinter import ttk, messagebox

# -------------------- CONFIG: DAILY POINTS TABLE --------------------
# daily_points[region][service_area] = points per day
DAILY_POINTS = {
    1: {1: 0.028, 2: 0.031, 3: 0.033, 4: 0.046, 5: 0.053, 6: 0.060},
    2: {1: 0.033, 2: 0.036, 3: 0.039, 4: 0.060, 5: 0.066, 6: 0.073},
    3: {1: 0.039, 2: 0.044, 3: 0.049, 4: 0.073, 5: 0.086, 6: 0.099},
}

# Competition / achievement point presets (optional)
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

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MEB Hizmet Puanı Hesaplayıcı (Tkinter)")
        self.geometry("860x560")
        self.minsize(860, 560)

        self.region_var = tk.IntVar(value=1)
        self.area_var = tk.IntVar(value=1)
        self.days_var = tk.StringVar(value="180")

        self.belletici_ybio_var = tk.StringVar(value="0")    # 0.2 each
        self.belletici_other_var = tk.StringVar(value="0")   # 0.1 each

        self.dyk_months_var = tk.StringVar(value="0")        # 0.5 per month
        self.talafi_months_var = tk.StringVar(value="0")     # 0.5 per month

        self.zumre_years_var = tk.StringVar(value="0")       # 1 per year (max 4)
        self.eba_scenario_var = tk.StringVar(value="0")      # 0.2 each (max 10/yr, user controls)
        self.eba_content_var = tk.StringVar(value="0")       # 0.3 each (max 10/yr, user controls)

        self.comp_var = tk.StringVar(value="Yok")
        self.manual_extra_var = tk.StringVar(value="0")      # optional extra

        self.result_var = tk.StringVar(value="Hazır")

        self._build_ui()
        self._update_daily_label()

    def _build_ui(self):
        pad = 10

        # Top frame: Base calc
        base = ttk.LabelFrame(self, text="1) Temel Puan (Hizmet Bölgesi + Hizmet Alanı + Gün Sayısı)")
        base.pack(fill="x", padx=pad, pady=(pad, 6))

        row = 0
        ttk.Label(base, text="Hizmet Bölgesi:").grid(row=row, column=0, sticky="w", padx=pad, pady=6)
        region_cb = ttk.Combobox(base, state="readonly", width=8,
                                 values=[1, 2, 3], textvariable=self.region_var)
        region_cb.grid(row=row, column=1, sticky="w", padx=(0, pad), pady=6)
        region_cb.bind("<<ComboboxSelected>>", lambda e: self._update_daily_label())

        ttk.Label(base, text="Hizmet Alanı (1-6):").grid(row=row, column=2, sticky="w", padx=pad, pady=6)
        area_cb = ttk.Combobox(base, state="readonly", width=8,
                               values=[1, 2, 3, 4, 5, 6], textvariable=self.area_var)
        area_cb.grid(row=row, column=3, sticky="w", padx=(0, pad), pady=6)
        area_cb.bind("<<ComboboxSelected>>", lambda e: self._update_daily_label())

        ttk.Label(base, text="Fiili Gün Sayısı:").grid(row=row, column=4, sticky="w", padx=pad, pady=6)
        ttk.Entry(base, textvariable=self.days_var, width=12).grid(row=row, column=5, sticky="w", padx=(0, pad), pady=6)

        row += 1
        self.daily_lbl = ttk.Label(base, text="Günlük puan: -")
        self.daily_lbl.grid(row=row, column=0, columnspan=6, sticky="w", padx=pad, pady=(0, 10))

        # Middle: extras
        extras = ttk.LabelFrame(self, text="2) Ek Puanlar (Yönetmelikteki kalemler)")
        extras.pack(fill="both", expand=True, padx=pad, pady=6)

        # Grid config
        for c in range(6):
            extras.grid_columnconfigure(c, weight=1)

        r = 0
        ttk.Label(extras, text="Belletici (YBO/Özel Eğitim Pansiyonu) görev sayısı (0.2/ görev):").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(extras, textvariable=self.belletici_ybio_var, width=10).grid(row=r, column=1, sticky="w", pady=6)
        ttk.Label(extras, text="Belletici (Diğer pansiyon) görev sayısı (0.1/ görev):").grid(row=r, column=2, sticky="w", padx=pad, pady=6)
        ttk.Entry(extras, textvariable=self.belletici_other_var, width=10).grid(row=r, column=3, sticky="w", pady=6)

        r += 1
        ttk.Label(extras, text="DYK/İYEP ay sayısı (0.5/ ay):").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(extras, textvariable=self.dyk_months_var, width=10).grid(row=r, column=1, sticky="w", pady=6)
        ttk.Label(extras, text="Telafi/Destek ay sayısı (0.5/ ay):").grid(row=r, column=2, sticky="w", padx=pad, pady=6)
        ttk.Entry(extras, textvariable=self.talafi_months_var, width=10).grid(row=r, column=3, sticky="w", pady=6)

        r += 1
        ttk.Label(extras, text="İl zümre başkanlığı yıl sayısı (1/ yıl, max 4):").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(extras, textvariable=self.zumre_years_var, width=10).grid(row=r, column=1, sticky="w", pady=6)

        ttk.Label(extras, text="EBA Senaryo sayısı (0.2/adet):").grid(row=r, column=2, sticky="w", padx=pad, pady=6)
        ttk.Entry(extras, textvariable=self.eba_scenario_var, width=10).grid(row=r, column=3, sticky="w", pady=6)

        r += 1
        ttk.Label(extras, text="EBA e-İçerik sayısı (0.3/adet):").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(extras, textvariable=self.eba_content_var, width=10).grid(row=r, column=1, sticky="w", pady=6)

        ttk.Label(extras, text="Yarışma/Ödül (tek ve en yüksek):").grid(row=r, column=2, sticky="w", padx=pad, pady=6)
        comp_cb = ttk.Combobox(extras, state="readonly", width=45, values=list(COMP_PRESETS.keys()), textvariable=self.comp_var)
        comp_cb.grid(row=r, column=3, columnspan=3, sticky="w", pady=6)

        r += 1
        ttk.Label(extras, text="Manuel ek puan (isteğe bağlı):").grid(row=r, column=0, sticky="w", padx=pad, pady=6)
        ttk.Entry(extras, textvariable=self.manual_extra_var, width=12).grid(row=r, column=1, sticky="w", pady=6)

        # Bottom actions
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=pad, pady=(6, pad))

        ttk.Button(bottom, text="Hesapla", command=self.calculate).pack(side="left")
        ttk.Button(bottom, text="Sıfırla", command=self.reset).pack(side="left", padx=8)

        ttk.Label(bottom, textvariable=self.result_var, font=("Segoe UI", 11, "bold")).pack(side="right")

        # Details text
        self.details = tk.Text(self, height=9, wrap="word")
        self.details.pack(fill="both", expand=False, padx=pad, pady=(0, pad))
        self.details.insert("1.0", "Detaylar burada görünecek...\n")
        self.details.configure(state="disabled")

    def _update_daily_label(self):
        region = self.region_var.get()
        area = self.area_var.get()
        daily = DAILY_POINTS.get(region, {}).get(area, None)
        if daily is None:
            self.daily_lbl.config(text="Günlük puan: -")
        else:
            self.daily_lbl.config(text=f"Günlük puan: {daily} (Bölge {region} / Alan {area})")

    def reset(self):
        self.region_var.set(1)
        self.area_var.set(1)
        self.days_var.set("365")
        self.belletici_ybio_var.set("0")
        self.belletici_other_var.set("0")
        self.dyk_months_var.set("0")
        self.talafi_months_var.set("0")
        self.zumre_years_var.set("0")
        self.eba_scenario_var.set("0")
        self.eba_content_var.set("0")
        self.comp_var.set("Yok")
        self.manual_extra_var.set("0")
        self.result_var.set("Hazır")
        self._update_daily_label()
        self._set_details("Detaylar burada görünecek...\n")

    def _set_details(self, text: str):
        self.details.configure(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", text)
        self.details.configure(state="disabled")

    def calculate(self):
        region = self.region_var.get()
        area = self.area_var.get()
        daily = DAILY_POINTS.get(region, {}).get(area)
        if daily is None:
            messagebox.showerror("Hata", "Geçersiz bölge/alan seçimi.")
            return

        days = safe_int(self.days_var.get(), -1)
        if days < 0:
            messagebox.showerror("Hata", "Fiili gün sayısı geçerli bir sayı olmalı.")
            return

        base_points = daily * days

        # extras
        bel_ybo = safe_int(self.belletici_ybio_var.get())
        bel_oth = safe_int(self.belletici_other_var.get())
        bel_points = bel_ybo * 0.2 + bel_oth * 0.1

        dyk_months = safe_int(self.dyk_months_var.get())
        talafi_months = safe_int(self.talafi_months_var.get())
        dyk_points = dyk_months * 0.5
        talafi_points = talafi_months * 0.5

        zumre_years = safe_int(self.zumre_years_var.get())
        if zumre_years > 4:
            zumre_years = 4  # management: cap
        zumre_points = zumre_years * 1.0

        eba_s = safe_int(self.eba_scenario_var.get())
        eba_c = safe_int(self.eba_content_var.get())
        eba_points = eba_s * 0.2 + eba_c * 0.3

        comp_points = COMP_PRESETS.get(self.comp_var.get(), 0)

        manual_extra = safe_float(self.manual_extra_var.get(), 0.0)

        total = base_points + bel_points + dyk_points + talafi_points + zumre_points + eba_points + comp_points + manual_extra

        self.result_var.set(f"Toplam: {total:.3f} puan")

        details = (
            f"--- TEMEL ---\n"
            f"Bölge: {region}, Alan: {area}\n"
            f"Günlük puan: {daily}\n"
            f"Gün: {days}\n"
            f"Temel puan = {daily} × {days} = {base_points:.3f}\n\n"
            f"--- EK PUANLAR ---\n"
            f"Belletici (0.2): {bel_ybo} görev → {bel_ybo*0.2:.3f}\n"
            f"Belletici (0.1): {bel_oth} görev → {bel_oth*0.1:.3f}\n"
            f"Belletici toplam: {bel_points:.3f}\n\n"
            f"DYK/İYEP: {dyk_months} ay → {dyk_points:.3f}\n"
            f"Telafi/Destek: {talafi_months} ay → {talafi_points:.3f}\n"
            f"İl zümre: {zumre_years} yıl (max 4) → {zumre_points:.3f}\n"
            f"EBA senaryo: {eba_s} → {eba_s*0.2:.3f}\n"
            f"EBA içerik: {eba_c} → {eba_c*0.3:.3f}\n"
            f"EBA toplam: {eba_points:.3f}\n"
            f"Yarışma/Ödül: {self.comp_var.get()} → {comp_points:.3f}\n"
            f"Manuel ek: {manual_extra:.3f}\n\n"
            f"=== GENEL TOPLAM: {total:.3f} ===\n"
        )
        self._set_details(details)

if __name__ == "__main__":
    # nicer look on Windows if available
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

    app = App()
    app.mainloop()
