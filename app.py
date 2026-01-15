import streamlit as st
import pandas as pd
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from io import BytesIO
from collections import defaultdict

# -------------------- CONFIG --------------------
st.set_page_config(page_title="Hizmet Puanı Hesaplayıcı", layout="wide")

# -------------------- HIDE MENU STYLE --------------------
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# -------------------- DAILY POINTS TABLE --------------------
DAILY_POINTS = {
    1: {1: 0.028, 2: 0.031, 3: 0.033, 4: 0.046, 5: 0.053, 6: 0.060},
    2: {1: 0.033, 2: 0.036, 3: 0.039, 4: 0.060, 5: 0.066, 6: 0.073},
    3: {1: 0.039, 2: 0.044, 3: 0.049, 4: 0.073, 5: 0.086, 6: 0.099},
}

# -------------------- EXTRA POINTS --------------------
STUDENT_AWARD_POINTS = {
    "Yok": {"1-3": 0, "4-6": 0},
    "Ulusal 1.": {"1-3": 15, "4-6": 20},
    "Ulusal 2.": {"1-3": 10, "4-6": 15},
    "Ulusal 3./Mansiyon": {"1-3": 5, "4-6": 10},
    "Uluslararası 1.": {"1-3": 30, "4-6": 40},
    "Uluslararası 2.": {"1-3": 20, "4-6": 30},
    "Uluslararası 3./Mansiyon": {"1-3": 10, "4-6": 20},
}
TEACHER_AWARD_POINTS = {
    "Yok": 0,
    "Ulusal 1.": 20,
    "Ulusal 2.": 15,
    "Ulusal 3./Mansiyon": 10,
    "Uluslararası 1.": 35,
    "Uluslararası 2.": 25,
    "Uluslararası 3./Mansiyon": 15,
}

KIND_LABELS = {
    "OFF_FULL": "İş günü sayılmayan (tam gün)",
    "OFF_HALF": "İş günü sayılmayan (yarım gün)",
    "COUNT_AS_WORKDAY": "İş günü sayılır (tören vb.)",
}

# -------------------- HELPERS --------------------
def parse_iso(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()

def daterange_inclusive(start: date, end: date):
    if end < start:
        start, end = end, start
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)

# -------------------- CALENDAR ENGINE --------------------
@dataclass
class CalendarRange:
    start: str  # YYYY-MM-DD
    end: str    # YYYY-MM-DD
    kind: str   # OFF_FULL / OFF_HALF / COUNT_AS_WORKDAY
    note: str = ""

def calendar_expand_effects(ranges: list[CalendarRange]):
    off_full, off_half, force_work = set(), set(), set()
    for r in ranges:
        s = parse_iso(r.start)
        e = parse_iso(r.end)
        for d in daterange_inclusive(s, e):
            if r.kind == "COUNT_AS_WORKDAY":
                force_work.add(d)
            elif r.kind == "OFF_FULL":
                off_full.add(d)
            elif r.kind == "OFF_HALF":
                off_half.add(d)
    # priority
    off_full -= force_work
    off_half -= force_work
    off_half -= off_full
    return off_full, off_half, force_work

def business_days_between(start: date, end: date, ranges: list[CalendarRange]) -> float:
    off_full, off_half, force_work = calendar_expand_effects(ranges)
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

# -------------------- TASK MODEL --------------------
@dataclass
class Task:
    year: int
    school: str
    region: int
    area: int
    mode: str  # "days" or "range"
    days: float
    start: str
    end: str

def default_calendar_2025_2026():
    return [
        CalendarRange("2025-11-10", "2025-11-14", "OFF_FULL", "Ara tatil"),
        CalendarRange("2026-01-19", "2026-01-30", "OFF_FULL", "Yarıyıl tatili"),
        CalendarRange("2026-03-16", "2026-03-20", "OFF_FULL", "Ara tatil"),
        CalendarRange("2026-03-19", "2026-03-22", "OFF_FULL", "Ramazan Bayramı (istersen 19 Mart'ı OFF_HALF yap)"),
        CalendarRange("2026-05-26", "2026-05-30", "OFF_FULL", "Kurban Bayramı"),
        CalendarRange("2025-10-29", "2025-10-29", "COUNT_AS_WORKDAY", "29 Ekim tören (iş günü sayılır)"),
        CalendarRange("2026-04-23", "2026-04-23", "COUNT_AS_WORKDAY", "23 Nisan tören (iş günü sayılır)"),
        CalendarRange("2026-05-19", "2026-05-19", "COUNT_AS_WORKDAY", "19 Mayıs tören (iş günü sayılır)"),
    ]

def init_state():
    if "tasks" not in st.session_state:
        st.session_state.tasks = [
            Task(
                year=2025,
                school="Okul/Kurum 1",
                region=1,
                area=1,
                mode="range",
                days=0.0,
                start="2025-09-08",
                end="2026-06-26",
            )
        ]
    if "cal_ranges" not in st.session_state:
        st.session_state.cal_ranges = default_calendar_2025_2026()
    if "calc_now" not in st.session_state:
        st.session_state.calc_now = False

init_state()

# -------------------- UI --------------------
st.title("Hizmet Puanı Hesaplayıcı")

with st.sidebar:
    st.header("Kontroller")
    expected_days = st.number_input("Yıl başına hedef iş günü (kontrol amaçlı)", min_value=0, value=180, step=1)

    st.divider()
    st.subheader("Ek Puanlar (Yönetmelik)")
    bel_ybo = st.number_input("Belletici YBO/Özel Eğitim (görev sayısı) → 0.2", min_value=0, value=0, step=1)
    bel_other = st.number_input("Belletici diğer pansiyon (görev sayısı) → 0.1", min_value=0, value=0, step=1)

    dyk_months = st.number_input("DYK/İYEP (ay) → 0.5/ay", min_value=0, value=0, step=1)
    telafi_months = st.number_input("Telafi/Destek (ay) → 0.5/ay", min_value=0, value=0, step=1)

    st.caption("Not: Telafi/Destek için aynı ay içinde birden fazla eğitim olsa bile yalnızca bir eğitim esas alınır (buraya ay sayısı giriyorsun).")

    st_student_award = st.selectbox("Öğrenci çalıştırma yarışması (tek ve en yüksek)", list(STUDENT_AWARD_POINTS.keys()), index=0)
    area_group = st.selectbox("Hizmet alanı grubu", ["1-3", "4-6"], index=0)

    teacher_award = st.selectbox("Öğretmenin kendi derecesi (tek ve en yüksek)", list(TEACHER_AWARD_POINTS.keys()), index=0)

    st.divider()
    st.subheader("EBA / İÇYS")
    eba_scenario = st.number_input("Senaryo→e-içerik adedi → 0.2 (Takvim yılı max 10)", min_value=0, value=0, step=1)
    eba_content = st.number_input("e-İçerik üretimi adedi → 0.3 (Takvim yılı max 10)", min_value=0, value=0, step=1)
    eba_ministry_assignment = st.checkbox("Bakanlık merkez/taşra görevlendirmesi ile e-içerik ürettim (puan yok)")

    st.divider()
    zumre_years = st.number_input("İl zümre başkanlığı yılı → 1/yıl (toplam max 4)", min_value=0, value=0, step=1)
    manual_extra = st.number_input("Manuel ek puan (isteğe bağlı)", value=0.0, step=0.5)

# -------------------- REPORT / DOWNLOAD HELPERS (GLOBAL) --------------------
def compute_report(tasks: list[Task]):
    warnings = []

    by_year_days = defaultdict(float)
    by_year_points = defaultdict(float)
    rows_detail = []

    for t in tasks:
        days = float(t.days)
        if t.mode == "range":
            try:
                s = parse_iso(t.start)
                e = parse_iso(t.end)
                days = business_days_between(s, e, st.session_state.cal_ranges)
            except Exception:
                warnings.append(f"{t.school}: tarih formatı hatalı, gün=0 varsayıldı.")
                days = 0.0

        daily = DAILY_POINTS.get(int(t.region), {}).get(int(t.area))
        if daily is None:
            warnings.append(f"{t.school}: bölge/alan seçimi geçersiz, puan=0 varsayıldı.")
            daily = 0.0

        pts = daily * days
        by_year_days[str(t.year)] += days
        by_year_points[str(t.year)] += pts

        rows_detail.append({
            "Yıl": int(t.year),
            "Okul/Kurum": t.school,
            "Bölge": int(t.region),
            "Alan": int(t.area),
            "Günlük Puan": daily,
            "İş günü": days,
            "Temel Puan": pts,
            "Mod": t.mode,
            "Başlangıç": t.start,
            "Bitiş": t.end,
        })

    base_total = sum(by_year_points.values())

    bel_points = bel_ybo * 0.2 + bel_other * 0.1
    dyk_points = dyk_months * 0.5
    tel_points = telafi_months * 0.5
    if telafi_months > 0:
        warnings.append("Telafi/Destek: ay içinde çok eğitim olsa bile tek eğitim esas (giriş ay sayısı).")

    student_points = STUDENT_AWARD_POINTS[st_student_award][area_group]
    if st_student_award != "Yok":
        warnings.append("Öğrenci yarışması: yalnızca bir defa ve en yüksek puan (tek seçim).")

    teacher_points = TEACHER_AWARD_POINTS[teacher_award]
    if teacher_award != "Yok":
        warnings.append("Öğretmen derecesi: yalnızca biri ve en yüksek puan (tek seçim).")

    eba_s_cap = min(int(eba_scenario), 10)
    eba_c_cap = min(int(eba_content), 10)
    if int(eba_scenario) > 10 or int(eba_content) > 10:
        warnings.append("EBA/İÇYS: takvim yılı içinde sayı 10’u geçemez; 10 ile sınırlandı.")
    if eba_ministry_assignment:
        eba_points = 0.0
        if eba_s_cap > 0 or eba_c_cap > 0:
            warnings.append("EBA/İÇYS: bakanlık görevlendirmesi ile üretimde puan yok; EBA puanı 0 alındı.")
    else:
        eba_points = eba_s_cap * 0.2 + eba_c_cap * 0.3

    z_years = min(int(zumre_years), 4)
    if int(zumre_years) > 4:
        warnings.append("İl zümre: toplam max 4 puan; 4 ile sınırlandı.")
    zumre_points = z_years * 1.0

    extras_total = bel_points + dyk_points + tel_points + student_points + teacher_points + eba_points + zumre_points + float(manual_extra)
    grand_total = base_total + extras_total

    for y, dsum in by_year_days.items():
        if expected_days and abs(dsum - expected_days) > 0.01:
            warnings.append(f"{y}: iş günü toplamı {dsum} (kontrol hedefi {expected_days}).")

    summary_rows = []
    for y in sorted(by_year_days.keys()):
        summary_rows.append({"Yıl": int(y), "Toplam İş günü": by_year_days[y], "Temel Puan": by_year_points[y]})

    extras_breakdown = [
        ("Belletici", bel_points),
        ("DYK/İYEP", dyk_points),
        ("Telafi/Destek", tel_points),
        ("Öğrenci Yarışması", student_points),
        ("Öğretmen Derecesi", teacher_points),
        ("EBA/İÇYS", eba_points),
        ("İl Zümre", zumre_points),
        ("Manuel Ek", float(manual_extra)),
        ("Ek Toplam", extras_total),
    ]

    meta = {"Temel Toplam": base_total, "Ek Toplam": extras_total, "Genel Toplam": grand_total}

    return (
        pd.DataFrame(rows_detail),
        pd.DataFrame(summary_rows),
        pd.DataFrame(extras_breakdown, columns=["Kalem", "Puan"]),
        meta,
        warnings,
    )

def to_excel_bytes(detail_df, year_df, extras_df, warnings_list, meta_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        detail_df.to_excel(writer, index=False, sheet_name="Gorevler")
        year_df.to_excel(writer, index=False, sheet_name="Yil_Ozet")
        extras_df.to_excel(writer, index=False, sheet_name="Ek_Puanlar")
        pd.DataFrame({"Uyari": warnings_list}).to_excel(writer, index=False, sheet_name="Uyarilar")
        pd.DataFrame(list(meta_dict.items()), columns=["Kalem", "Deger"]).to_excel(writer, index=False, sheet_name="Toplamlar")
        cal_df = pd.DataFrame([asdict(r) for r in st.session_state.cal_ranges])
        if not cal_df.empty:
            cal_df.to_excel(writer, index=False, sheet_name="Takvim")
    output.seek(0)
    return output.getvalue()

# -------------------- TABS --------------------
tab1, tab2 = st.tabs(["Görevler / Okullar", "Takvim / Tatiller"])

with tab1:
    st.subheader("Görevler / Okullar")

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("➕ Görev ekle"):
            st.session_state.tasks.append(
                Task(
                    year=2025,
                    school=f"Okul/Kurum {len(st.session_state.tasks) + 1}",
                    region=1,
                    area=1,
                    mode="range",
                    days=0.0,
                    start="2025-09-08",
                    end="2026-06-26",
                )
            )
    with c2:
        if st.button("🧹 Tüm görevleri sıfırla"):
            st.session_state.tasks = [Task(2025, "Okul/Kurum 1", 1, 1, "range", 0.0, "2025-09-08", "2026-06-26")]
            st.session_state.calc_now = False

    st.write("Her satır bir görev/kurum kaydıdır. Yıl içinde farklı okullar varsa ayrı satır aç.")

    for i, t in enumerate(st.session_state.tasks):
        with st.expander(f"#{i+1} — {t.school}", expanded=True):
            colA, colB, colC, colD = st.columns([1, 2, 1, 1])
            with colA:
                t.year = st.number_input(f"Yıl (#{i+1})", min_value=1900, max_value=2100, value=int(t.year), step=1, key=f"year_{i}")
            with colB:
                t.school = st.text_input(f"Okul/Kurum adı (#{i+1})", value=t.school, key=f"school_{i}")
            with colC:
                t.region = st.selectbox(f"Bölge (#{i+1})", [1, 2, 3], index=[1,2,3].index(t.region), key=f"region_{i}")
            with colD:
                t.area = st.selectbox(f"Alan (#{i+1})", [1,2,3,4,5,6], index=[1,2,3,4,5,6].index(t.area), key=f"area_{i}")

            mode = st.radio(
                f"Fiili süre girişi (#{i+1})",
                ["Tarih aralığı", "Gün gir"],
                index=0 if t.mode == "range" else 1,
                horizontal=True,
                key=f"mode_{i}",
            )
            t.mode = "range" if mode == "Tarih aralığı" else "days"

            if t.mode == "range":
                col1, col2, col3 = st.columns([1, 1, 1])
                with col1:
                    t.start = st.text_input("Başlangıç (YYYY-MM-DD)", value=t.start, key=f"start_{i}")
                with col2:
                    t.end = st.text_input("Bitiş (YYYY-MM-DD)", value=t.end, key=f"end_{i}")
                with col3:
                    if st.button("📅 İş gününü hesapla", key=f"calc_days_{i}"):
                        try:
                            s = parse_iso(t.start)
                            e = parse_iso(t.end)
                            t.days = business_days_between(s, e, st.session_state.cal_ranges)
                            st.success(f"Hesaplanan iş günü: {t.days}")
                        except Exception as ex:
                            st.error(f"Tarih formatı hatalı: {ex}")
                st.caption("İş günü hesabı: hafta sonu düşer, Takvim/Tatil aralıkları uygulanır.")
            else:
                t.days = st.number_input("Bu kurumda iş günü (manuel)", min_value=0.0, value=float(t.days), step=1.0, key=f"days_{i}")

            if st.button("🗑 Bu görevi sil", key=f"del_{i}"):
                st.session_state.tasks.pop(i)
                st.session_state.calc_now = False
                st.rerun()

    # -------- NEW: bottom calculate button + inline report --------
    st.divider()
    st.subheader("Hesaplama")

    if st.button("🧮 Hizmet Puanı Hesapla", width='content'):
        st.session_state.calc_now = True

    if st.session_state.calc_now:
        detail_df, year_df, extras_df, meta, warnings = compute_report(st.session_state.tasks)

        st.markdown("### Özet")
        m1, m2, m3 = st.columns(3)
        m1.metric("Temel Toplam", f"{meta['Temel Toplam']:.3f}")
        m2.metric("Ek Toplam", f"{meta['Ek Toplam']:.3f}")
        m3.metric("Genel Toplam", f"{meta['Genel Toplam']:.3f}")

        if warnings:
            st.markdown("### Uyarılar")
            for w in warnings[:12]:
                st.warning(w)
            if len(warnings) > 12:
                st.info(f"{len(warnings)-12} uyarı daha var (Excel'de tamamı var).")
        else:
            st.success("Uyarı yok.")

        st.markdown("### Yıl Bazlı Temel Puan")
        st.dataframe(year_df, width='content')

        st.markdown("### Ek Puanlar")
        st.dataframe(extras_df, width='content')

        st.markdown("### Görev Detayları")
        st.dataframe(detail_df, width='content')

        excel_bytes = to_excel_bytes(detail_df, year_df, extras_df, warnings, meta)

        d1, d2 = st.columns([1, 1])
        with d1:
            st.download_button(
                label="⬇️ Excel olarak indir (.xlsx)",
                data=excel_bytes,
                file_name="hizmet_puani_raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_excel_tab1",   # ✅ eklendi
            )
        with d2:
            st.download_button(
                label="⬇️ Görev Detaylarını CSV indir",
                data=detail_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="gorev_detaylari.csv",
                mime="text/csv",
                use_container_width=True,
                key="dl_csv_tab1",     # ✅ eklendi
            )

with tab2:
    st.subheader("Takvim / Tatiller (Düzenlenebilir)")
    st.write("İş günü hesabında kullanılacak tatil/istisna aralıklarını burada yönet.")

    with st.expander("➕ Yeni takvim aralığı ekle", expanded=True):
        col1, col2, col3, col4 = st.columns([1, 1, 1.6, 1.4])
        with col1:
            c_start = st.text_input("Başlangıç", value="2026-03-19")
        with col2:
            c_end = st.text_input("Bitiş", value="2026-03-22")
        with col3:
            kind = st.selectbox("Tür", list(KIND_LABELS.keys()), format_func=lambda k: f"{k} — {KIND_LABELS[k]}")
        with col4:
            note = st.text_input("Açıklama", value="Örnek tatil")
        if st.button("Ekle"):
            try:
                parse_iso(c_start); parse_iso(c_end)
                st.session_state.cal_ranges.append(CalendarRange(c_start, c_end, kind, note))
                st.success("Eklendi.")
            except Exception as ex:
                st.error(f"Tarih formatı hatalı: {ex}")

    st.divider()

    cal_df = pd.DataFrame([asdict(r) for r in st.session_state.cal_ranges])
    if not cal_df.empty:
        cal_df["kind_label"] = cal_df["kind"].map(KIND_LABELS)
        st.dataframe(cal_df[["start", "end", "kind_label", "note"]], width='content')

        del_idx = st.number_input(
            "Silmek istediğin satır numarası (1'den başlar)",
            min_value=0,
            max_value=len(st.session_state.cal_ranges),
            value=0,
            step=1,
            help="0 girersen silme yapmaz.",
        )
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("🗑 Seçiliyi sil"):
                if del_idx > 0:
                    st.session_state.cal_ranges.pop(del_idx - 1)
                    st.session_state.calc_now = False
                    st.success("Silindi.")
                else:
                    st.info("Silmek için 1..N arası bir numara gir.")
        with c2:
            if st.button("↺ Varsayılan 2025–2026 takvimini yükle"):
                st.session_state.cal_ranges = default_calendar_2025_2026()
                st.session_state.calc_now = False
                st.success("Varsayılan takvim yüklendi.")
    else:
        st.info("Takvim listesi boş.")

# with tab3:
#     st.subheader("Rapor / İndir")
#     detail_df, year_df, extras_df, meta, warnings = compute_report(st.session_state.tasks)

#     c1, c2 = st.columns([1.1, 1])
#     with c1:
#         st.markdown("### Özet")
#         st.metric("Temel Toplam", f"{meta['Temel Toplam']:.3f}")
#         st.metric("Ek Toplam", f"{meta['Ek Toplam']:.3f}")
#         st.metric("Genel Toplam", f"{meta['Genel Toplam']:.3f}")

#     with c2:
#         if warnings:
#             st.markdown("### Uyarılar")
#             for w in warnings[:12]:
#                 st.warning(w)
#             if len(warnings) > 12:
#                 st.info(f"{len(warnings)-12} uyarı daha var (indirilen raporda hepsi var).")
#         else:
#             st.success("Uyarı yok.")

#     st.markdown("### Yıl Bazlı Temel Puan")
#     st.dataframe(year_df, width='content')

#     st.markdown("### Ek Puanlar")
#     st.dataframe(extras_df, width='content')

#     st.markdown("### Görev Detayları")
#     st.dataframe(detail_df, width='content')

#     excel_bytes = to_excel_bytes(detail_df, year_df, extras_df, warnings, meta)

#     st.download_button(
#     label="⬇️ Excel olarak indir (.xlsx)",
#     data=excel_bytes,
#     file_name="hizmet_puani_raporu.xlsx",
#     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#     key="dl_excel_tab3",   # ✅ eklendi
#     )

#     st.download_button(
#         label="⬇️ Görev Detaylarını CSV indir",
#         data=detail_df.to_csv(index=False).encode("utf-8-sig"),
#         file_name="gorev_detaylari.csv",
#         mime="text/csv",
#         key="dl_csv_tab3",     # ✅ eklendi
#     )

