import re
from pathlib import Path
import streamlit as st

from app.search import (
    keyword_search,
    list_top_entities,
    search_entity_mentions,
    list_top_assets,
    search_asset_mentions,
    list_events,
    get_event_detail,
)

from app.network import build_network_exposure
from app.pdd import analyze_overlap_randomness
from app.ree import ingest_registry_folder, lookup_registry_records

DB = Path("data/index/forensic.db")
REG_DIR = Path("data/registries")

def snippet_around(text: str, needle: str, window: int = 220) -> str:
    if not text or not needle:
        return (text or "")[:500]
    m = re.search(re.escape(needle), text, flags=re.IGNORECASE)
    if not m:
        return text[:500]
    start = max(0, m.start() - window)
    end = min(len(text), m.end() + window)
    return text[start:end]

st.set_page_config(page_title="Forensic Browser", layout="wide")
st.title("Forensic Browser")
st.caption("Evidence-first search + structured pattern exposure (offline). No face identification. No accusations.")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Keyword Search",
    "Entities & Assets",
    "Network Exposure (NEM)",
    "PDD (Overlap/Randomness)",
    "Registry Expansion (REE)"
])

# -------------------------
# Keyword Search
# -------------------------
with tab1:
    st.subheader("Keyword Search (FTS5)")
    q = st.text_input("Enter keywords (quotes for phrase search)", placeholder='Example: "John Smith" flight OR island')
    limit = st.slider("Max results", 20, 500, 200, step=20)

    if q:
        results = keyword_search(DB, q, limit=limit)
        st.write(f"Results: {len(results)}")
        for fname, page, snip in results:
            st.markdown(f"**{fname} — Page {page}**")
            st.code(snip)

# -------------------------
# Entities & Assets
# -------------------------
with tab2:
    st.subheader("Entities & Assets Explorer")

    colA, colB = st.columns(2)

    with colA:
        st.markdown("### Entity Explorer")
        label = st.selectbox("Entity type", ["PERSON", "ORG", "GPE", "LOC", "DATE", "EMAIL", "PHONE", "URL"])
        topn = st.slider("Top entities", 20, 400, 100, step=20, key="top_entities")

        ents = list_top_entities(DB, label=label, limit=topn)
        if ents:
            options = [f"{t}  (count={c})" for (t, _lbl, c) in ents]
            selected = st.selectbox("Pick an entity", options)
            ent_text = selected.split("  (count=")[0]

            mentions = search_entity_mentions(DB, ent_text, label=label, limit=300)
            st.write(f"Mentions: {len(mentions)}")
            for fname, page, content in mentions:
                st.markdown(f"**{fname} — Page {page}**")
                st.code(snippet_around(content, ent_text))
        else:
            st.info("No entities found yet. Ingest data first.")

    with colB:
        st.markdown("### Asset Explorer")
        asset_type = st.selectbox("Asset type", ["AIRCRAFT_REG", "IMO"], key="asset_type")
        topa = st.slider("Top assets", 10, 200, 50, step=10, key="top_assets")

        assets = list_top_assets(DB, asset_type=asset_type, limit=topa)
        if assets:
            aopts = [f"{v}  (count={c})" for (v, _t, c) in assets]
            aselected = st.selectbox("Pick an asset", aopts)
            aval = aselected.split("  (count=")[0]

            am = search_asset_mentions(DB, aval, asset_type=asset_type, limit=300)
            st.write(f"Mentions: {len(am)}")
            for fname, page, content in am:
                st.markdown(f"**{fname} — Page {page}**")
                st.code(snippet_around(content, aval))
        else:
            st.info("No assets found yet. Ensure ingestion ran and the dataset contains recognizable asset patterns.")

    st.markdown("---")
    st.markdown("### Derived Events (DATE + LOCATION on same page)")
    evs = list_events(DB, limit=50)
    if evs:
        ev_sel = st.selectbox("Pick an event", [f"#{eid} | {dt} | {loc} | {fn}:{pg}" for (eid, dt, loc, fn, pg) in evs])
        ev_id = int(ev_sel.split("|")[0].strip().lstrip("#"))
        detail = get_event_detail(DB, ev_id)
        if detail:
            st.json(detail)
    else:
        st.info("No derived events yet. Events require DATE + LOCATION on the same page.")

# -------------------------
# Network Exposure Module (NEM)
# -------------------------
with tab3:
    st.subheader("Network Exposure (NEM)")
    st.write("This exposes structural overlap without identifying faces or asserting intent/guilt.")

    focus = st.text_input("Optional focus entity text (exact match as stored)", placeholder="Leave blank for global structure summary")
    max_assets = st.slider("Max repeated assets to show", 5, 30, 10, step=5)
    max_events = st.slider("Max events to analyze", 10, 200, 50, step=10)

    if st.button("Run NEM"):
        res = build_network_exposure(DB, focus_entity_text=focus.strip() or None, max_assets=max_assets, max_events=max_events)
        for s in res.statements:
            st.markdown(f"**{s.statement_type.value}** (confidence={s.confidence_score:.2f})")
            st.write(s.text)
            if s.primary_sources:
                st.caption("Primary sources:")
                for src in s.primary_sources:
                    st.code(f"{src.filename} p{src.page}: {src.snippet}")
            if s.metadata:
                st.caption("Metadata:")
                st.json(s.metadata)

# -------------------------
# PDD
# -------------------------
with tab4:
    st.subheader("PDD — Plausible Deniability Destroyer")
    st.write("Computes overlap counts and a conservative randomness framing. No accusations.")

    a = st.text_input("Entity A (exact text)")
    b = st.text_input("Entity B (exact text)")
    scope = st.selectbox("Scope", ["EVENTS", "DOCS"])

    if st.button("Analyze overlap"):
        out = analyze_overlap_randomness(DB, entity_a=a.strip(), entity_b=b.strip(), scope=scope)
        for s in out.statements:
            st.markdown(f"**{s.statement_type.value}** (confidence={s.confidence_score:.2f})")
            st.write(s.text)
            if s.metadata:
                st.json(s.metadata)

# -------------------------
# REE
# -------------------------
with tab5:
    st.subheader("Registry Expansion Engine (REE) — Offline-first")
    st.write("Load local registry CSV datasets from `data/registries/` and link FACT records to entities/assets. No scraping.")

    st.code(
        "CSV required columns:\n"
        "registry_name,record_type,subject_type,subject_value,field_key,field_value,primary_source\n"
        "Optional: secondary_source\n\n"
        "subject_type must be ENTITY or ASSET"
    )

    REG_DIR.mkdir(parents=True, exist_ok=True)

    if st.button("Ingest registry CSVs now"):
        report = ingest_registry_folder(DB, REG_DIR)
        st.json(report.__dict__)

    st.markdown("### Lookup registry records")
    subj_type = st.selectbox("Subject type", ["ENTITY", "ASSET"])
    subj_val = st.text_input("Subject value (exact string you used in registry CSV)")
    if st.button("Lookup"):
        rows = lookup_registry_records(DB, subj_type, subj_val)
        st.json(rows)
