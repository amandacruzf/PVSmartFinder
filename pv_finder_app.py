# pv_finder_app.py
# Streamlit app: PV Finder – Intelligent Packaging Specification Search (PepsiCo-themed)

import io
import datetime as dt
from typing import List, Dict
import re
import pandas as pd
import streamlit as st

# =========================
# Required columns & aliases
# =========================
REQUIRED_COLUMNS: List[str] = [
    "PVNumber","PVStatus","Description","DocumentType","NoteForMarketing",
    "CaseTypeDescriptor","AirFillDescriptor","CodeDate","SalesClass","Size",
    "Shape","CasesPerLayer(TI)","HI(Layers/Pallet)",
    "TotalNumberOfCasesPerPallet","BagsOrTraysPerLayer",
]

HEADER_ALIASES: Dict[str, str] = {
    "PVNumber": r"pv number|pv_number|pv no|pvno|pv num|pv id",
    "PVStatus": r"pv status|status|pv details|pv_status",
    "Description": r"description|desc|product description",
    "DocumentType": r"document type|doctype|doc type|doc_type",
    "NoteForMarketing": r"note for marketing|marketing note|notes marketing|note_marketing",
    "CaseTypeDescriptor": r"case type descriptor|case type|case descriptor",
    "AirFillDescriptor": r"air fill descriptor|airfill descriptor|air fill|air_fill",
    "CodeDate": r"code date|codedate|code_date|date code|mfg date",
    "SalesClass": r"sales class|sales_class|class",
    "Size": r"size|pack size|net weight|weight",
    "Shape": r"shape|format",
    "CasesPerLayer(TI)": r"cases per layer|cases/layer|ti|cases_per_layer|cases per layer \(ti\)",
    "HI(Layers/Pallet)": r"hi|layers per pallet|layers/pallet|layers_per_pallet",
    "TotalNumberOfCasesPerPallet": r"total cases per pallet|total number of cases per pallet|total cases/pallet",
    "BagsOrTraysPerLayer": r"bags per layer|trays per layer|bags_or_trays_per_layer|bags/trays per layer",
}

st.set_page_config(page_title="PV Finder – Packaging Specs", layout="wide")

PEPSICO_BLUE = "#004C97"
st.markdown('''
<style>
  .pepsico-header {display:flex;align-items:center;gap:12px;padding:12px 0 6px 0;border-bottom:3px solid #004C9733;}
  .pill {background:#004C97;color:white;padding:2px 10px;border-radius:999px;font-size:12px;}
</style>
''', unsafe_allow_html=True)

if "last_updated" not in st.session_state:
    st.session_state.last_updated = None

st.markdown("<div class='pepsico-header'><h1 style='margin:0;color:#004C97'>PV Finder <span class='pill'>Packaging Specs</span></h1></div>", unsafe_allow_html=True)
st.caption(f"Last updated: {st.session_state.last_updated or '—'}")
st.caption("Type any fragment of PV number, description or notes. Update the base weekly via upload (Admin).")

def _strip_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={c: c.strip() for c in df.columns})

def _apply_header_aliases(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    lowered = {c.lower(): c for c in df.columns}
    for canon, pattern in HEADER_ALIASES.items():
        if canon in df.columns:
            continue
        regex = re.compile(rf"^(?:{pattern})$", re.IGNORECASE)
        for low, orig in lowered.items():
            if regex.match(low):
                rename_map[orig] = canon
                break
    return df.rename(columns=rename_map)

def _ensure_required(df: pd.DataFrame) -> pd.DataFrame:
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[REQUIRED_COLUMNS].copy()

def _parse_code_date_numeric(df: pd.DataFrame) -> pd.DataFrame:
    if "CodeDate" in df.columns:
        df["CodeDate_num"] = pd.to_numeric(df["CodeDate"], errors="coerce")
    else:
        df["CodeDate_num"] = pd.NA
    return df

def _latest_per_pv_flag(df: pd.DataFrame) -> pd.DataFrame:
    if "PVNumber" not in df.columns:
        df["IsLatestPerPV"] = False
        return df
    tmp = df.copy()
    tmp.sort_values(["PVNumber","CodeDate_num"], ascending=[True,False], inplace=True)
    tmp["IsLatestPerPV"] = ~tmp.duplicated(subset=["PVNumber"], keep="first")
    return tmp

def _download_xlsx(df: pd.DataFrame, filename: str):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
    st.download_button("⬇️ Download XLSX", data=out.getvalue(), file_name=filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def _download_csv(df: pd.DataFrame, filename: str):
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Download CSV", data=csv, file_name=filename, mime="text/csv")

st.sidebar.header("Admin – Weekly Upload")
use_pin = st.sidebar.toggle("Protect upload with PIN", value=True)
allow_upload = True
if use_pin:
    pin_input = st.sidebar.text_input("Enter PIN", type="password")
    admin_pin = st.secrets.get("ADMIN_PIN", "130125")  # default PIN configured
    allow_upload = (pin_input == admin_pin)
    if pin_input and not allow_upload:
        st.sidebar.warning("Incorrect PIN. Upload blocked.")

uploaded_df = None
if allow_upload:
    up = st.sidebar.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
    if up is not None:
        try:
            df = pd.read_excel(up)
            df = _strip_columns(df)
            df = _apply_header_aliases(df)
            df = _ensure_required(df)
            df = _parse_code_date_numeric(df)
            df = _latest_per_pv_flag(df)
            uploaded_df = df
            st.session_state.last_updated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            st.sidebar.success("Base loaded successfully!")
        except Exception as e:
            st.sidebar.error(f"Failed to read Excel: {e}")
else:
    st.sidebar.info("Enter correct PIN to upload.")

if uploaded_df is None:
    st.info("Upload a valid Excel to start. You can also download a blank template from the home folder.")
    st.stop()

if "defaults" not in st.session_state:
    st.session_state.defaults = {}

c1,c2,c3 = st.columns([1,1,1])
with c1:
    if st.button("Reset"):
        for k in ["query","basic_filters","adv_filters","keep_latest_only","date_range"]:
            if k in st.session_state: del st.session_state[k]
        st.rerun()
with c2:
    if st.button("Save defaults"):
        st.session_state.defaults = {
            "query": st.session_state.get("query",""),
            "basic_filters": st.session_state.get("basic_filters",{}),
            "adv_filters": st.session_state.get("adv_filters",{}),
            "keep_latest_only": st.session_state.get("keep_latest_only",False),
            "date_range": st.session_state.get("date_range",None),
        }
        st.success("Defaults saved for this browser session.")
with c3:
    if st.button("Load defaults"):
        d = st.session_state.get("defaults",{})
        st.session_state.query = d.get("query","")
        st.session_state.basic_filters = d.get("basic_filters",{})
        st.session_state.adv_filters = d.get("adv_filters",{})
        st.session_state.keep_latest_only = d.get("keep_latest_only",False)
        st.session_state.date_range = d.get("date_range",None)
        st.success("Defaults loaded.")

base = uploaded_df.copy()

st.text_input(
    "Global search (fragment across ALL columns)",
    key="query",
    placeholder="e.g., 'Doritos', 'C2', 'X-Dock', 'Walmart', 'Display', 'P00'",
)

st.subheader("Basic column filters (optional)")
_bf = st.session_state.get("basic_filters", {})
new_bf = {}

basic_cols = ["PVNumber","PVStatus","DocumentType","CaseTypeDescriptor","SalesClass","Shape","Size"]
bcols = st.columns(len(basic_cols))
for i, col in enumerate(basic_cols):
    options = sorted(base[col].dropna().astype(str).unique()) if col in base.columns else []
    with bcols[i]:
        new_bf[col] = st.multiselect(col, options, default=_bf.get(col, []))
st.session_state.basic_filters = new_bf

with st.expander("Advanced filters (choose any column)", expanded=False):
    _af = st.session_state.get("adv_filters", {})
    new_af = {}
    all_cols = REQUIRED_COLUMNS
    for col in all_cols:
        cc1, cc2 = st.columns([1,1])
        with cc1:
            mode = st.selectbox(
                f"{col} operator",
                ["(none)", "contains", "equals", "in list"],
                index=["(none)", "contains", "equals", "in list"].index(_af.get(col, {}).get("mode","(none)"))
            )
        with cc2:
            value = st.text_input(
                f"{col} value",
                value=_af.get(col, {}).get("value",""),
                placeholder="For 'in list', separate by ;"
            )
        if mode != "(none)" and value:
            new_af[col] = {"mode": mode, "value": value}
    st.session_state.adv_filters = new_af

left, right = st.columns([1,1])
with left:
    keep_latest_only = st.toggle("Keep only latest per PVNumber", value=st.session_state.get("keep_latest_only", False))
    st.session_state.keep_latest_only = keep_latest_only
with right:
    if base["CodeDate_num"].notna().any():
        min_v = int(pd.to_numeric(base["CodeDate_num"], errors="coerce").min())
        max_v = int(pd.to_numeric(base["CodeDate_num"], errors="coerce").max())
        dv1, dv2 = st.columns(2)
        with dv1:
            min_str = st.text_input("Code Date min (numeric)", value=str(min_v))
        with dv2:
            max_str = st.text_input("Code Date max (numeric)", value=str(max_v))
    else:
        min_str = max_str = ""

q = st.session_state.get("query","").strip().lower()
mask = pd.Series(True, index=base.index)
if q:
    mm = pd.Series(False, index=base.index)
    for col in REQUIRED_COLUMNS:
        mm = mm | base[col].astype(str).str.lower().str.contains(q, na=False)
    mask &= mm

for col, selected in st.session_state.basic_filters.items():
    if selected:
        mask &= base[col].astype(str).isin(selected)

for col, cond in st.session_state.adv_filters.items():
    mode = cond["mode"]; val = cond["value"]
    series = base[col].astype(str)
    if mode == "contains":
        mask &= series.str.contains(val, case=False, na=False)
    elif mode == "equals":
        mask &= series.str.lower() == val.lower()
    elif mode == "in list":
        items = [v.strip() for v in val.split(";") if v.strip()]
        mask &= series.isin(items)

if min_str and max_str:
    try:
        min_n = float(min_str); max_n = float(max_str)
        mask &= (base["CodeDate_num"].astype(float) >= min_n) & (base["CodeDate_num"].astype(float) <= max_n)
    except Exception:
        pass

filtered = base[mask].copy()
if keep_latest_only:
    filtered.sort_values(["PVNumber","CodeDate_num"], ascending=[True, False], inplace=True)
    filtered = filtered.drop_duplicates(subset=["PVNumber"], keep="first")

display_df = filtered[REQUIRED_COLUMNS].copy()
display_df["CodeDate (num)"] = filtered["CodeDate_num"]

st.write(f"Results: **{len(display_df)}** records")
st.dataframe(display_df, use_container_width=True, hide_index=True)

_download_xlsx(display_df, "PV_Finder_Results.xlsx")
_download_csv(display_df, "PV_Finder_Results.csv")
