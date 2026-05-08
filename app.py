import streamlit as st
from groq import Groq
import json
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime

# ── Groq client via Streamlit secrets ────────────────────────────────────────
# Add to .streamlit/secrets.toml:
#   GROQ_API_KEY = "your_groq_api_key_here"
def get_groq_client():
    return Groq(api_key=st.secrets["GROQ_API_KEY"])

GROQ_MODEL = "llama-3.3-70b-versatile"

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GembaIQ",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .main { background-color: #0f1117; }

    .metric-card {
        background: linear-gradient(135deg, #1a1d27 0%, #22263a 100%);
        border: 1px solid #2d3147;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
    }
    .metric-label {
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        color: #6b7280;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 36px;
        font-weight: 700;
        color: #f9fafb;
        line-height: 1;
    }
    .metric-sub {
        font-size: 12px;
        color: #9ca3af;
        margin-top: 4px;
    }

    .oee-world-class { color: #10b981 !important; }
    .oee-good        { color: #3b82f6 !important; }
    .oee-typical     { color: #f59e0b !important; }
    .oee-poor        { color: #ef4444 !important; }

    .kaizen-card {
        background: #1a1d27;
        border: 1px solid #2d3147;
        border-left: 4px solid #6366f1;
        border-radius: 10px;
        padding: 18px 22px;
        margin-bottom: 14px;
    }
    .kaizen-rank {
        display: inline-block;
        background: #6366f1;
        color: white;
        font-size: 11px;
        font-weight: 700;
        padding: 2px 10px;
        border-radius: 20px;
        margin-bottom: 8px;
    }
    .kaizen-title {
        font-size: 16px;
        font-weight: 600;
        color: #f9fafb;
        margin-bottom: 10px;
    }
    .kaizen-row {
        display: flex;
        gap: 24px;
        flex-wrap: wrap;
        margin-top: 10px;
    }
    .kaizen-pill {
        background: #22263a;
        border: 1px solid #374151;
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 12px;
        color: #d1d5db;
    }

    .handover-box {
        background: #1a1d27;
        border: 1px solid #2d3147;
        border-radius: 10px;
        padding: 20px 24px;
        font-size: 14px;
        line-height: 1.7;
        color: #e5e7eb;
        white-space: pre-wrap;
    }

    .loss-badge-downtime { background: #7f1d1d; color: #fca5a5; border-radius: 4px; padding: 2px 8px; font-size: 11px; }
    .loss-badge-speed    { background: #78350f; color: #fcd34d; border-radius: 4px; padding: 2px 8px; font-size: 11px; }
    .loss-badge-quality  { background: #1e3a5f; color: #93c5fd; border-radius: 4px; padding: 2px 8px; font-size: 11px; }

    .section-header {
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
        color: #6366f1;
        margin-bottom: 12px;
        padding-bottom: 6px;
        border-bottom: 1px solid #2d3147;
    }
    .stButton>button {
        background: linear-gradient(135deg, #6366f1, #4f46e5);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 10px 28px;
        font-size: 14px;
        width: 100%;
    }
    .stButton>button:hover { background: linear-gradient(135deg, #4f46e5, #4338ca); }
    div[data-testid="stSidebar"] { background: #0d0f18; border-right: 1px solid #1f2937; }
</style>
""", unsafe_allow_html=True)


# ── OEE Calculation ───────────────────────────────────────────────────────────
def calculate_oee(planned_mins, unplanned_down, planned_down,
                  ideal_cycle_secs, total_count, good_count):
    operating_time = planned_mins - unplanned_down - planned_down
    if operating_time <= 0 or planned_mins <= 0:
        return None

    availability  = operating_time / planned_mins
    ideal_time    = (ideal_cycle_secs / 60) * total_count          # mins
    performance   = min(ideal_time / operating_time, 1.0) if operating_time > 0 else 0
    quality       = good_count / total_count if total_count > 0 else 0

    return {
        "availability":     round(availability,  4),
        "performance":      round(performance,   4),
        "quality":          round(quality,        4),
        "oee":              round(availability * performance * quality, 4),
        "operating_time":   operating_time,
        "planned_mins":     planned_mins,
        "total_count":      total_count,
        "good_count":       good_count,
        "defects":          total_count - good_count,
    }


# ── Six Big Losses ────────────────────────────────────────────────────────────
def get_six_losses(oee, breakdown_mins, setup_mins,
                   minor_stop_mins, speed_loss_pct, defect_count, startup_defects):
    losses = []
    planned = oee["planned_mins"]

    if breakdown_mins > 0:
        losses.append({"loss": "Equipment Breakdowns",   "type": "Downtime",  "minutes": breakdown_mins,
                        "pct": round(breakdown_mins / planned * 100, 1)})
    if setup_mins > 0:
        losses.append({"loss": "Setup & Adjustments",    "type": "Downtime",  "minutes": setup_mins,
                        "pct": round(setup_mins / planned * 100, 1)})
    if minor_stop_mins > 0:
        losses.append({"loss": "Minor Stops & Idling",   "type": "Speed",     "minutes": minor_stop_mins,
                        "pct": round(minor_stop_mins / planned * 100, 1)})
    if speed_loss_pct > 0:
        sl_mins = oee["operating_time"] * (speed_loss_pct / 100)
        losses.append({"loss": "Reduced Speed",          "type": "Speed",     "minutes": round(sl_mins, 1),
                        "pct": round(sl_mins / planned * 100, 1)})
    if defect_count > 0:
        dl_mins = defect_count * (oee["operating_time"] / oee["total_count"]) if oee["total_count"] > 0 else 0
        losses.append({"loss": "Defects & Rework",       "type": "Quality",   "minutes": round(dl_mins, 1),
                        "pct": round(dl_mins / planned * 100, 1)})
    if startup_defects > 0:
        losses.append({"loss": "Startup / Yield Losses", "type": "Quality",   "minutes": startup_defects * 2,
                        "pct": round(startup_defects * 2 / planned * 100, 1)})

    return sorted(losses, key=lambda x: x["minutes"], reverse=True)


# ── OEE Gauge ─────────────────────────────────────────────────────────────────
def oee_gauge(value, label):
    color = "#10b981" if value >= 0.85 else "#3b82f6" if value >= 0.70 else "#f59e0b" if value >= 0.50 else "#ef4444"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(value * 100, 1),
        number={"suffix": "%", "font": {"size": 28, "color": "#f9fafb", "family": "Inter"}},
        title={"text": label, "font": {"size": 13, "color": "#9ca3af", "family": "Inter"}},
        gauge={
            "axis":      {"range": [0, 100], "tickfont": {"color": "#6b7280", "size": 10}},
            "bar":       {"color": color},
            "bgcolor":   "#1a1d27",
            "bordercolor": "#374151",
            "steps": [
                {"range": [0,  50],  "color": "#1a1d27"},
                {"range": [50, 70],  "color": "#1f2128"},
                {"range": [70, 85],  "color": "#1f2435"},
                {"range": [85, 100], "color": "#1a2635"},
            ],
            "threshold": {"line": {"color": "#6366f1", "width": 2}, "value": 85},
        }
    ))
    fig.update_layout(height=200, margin=dict(t=30, b=10, l=20, r=20),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


# ── AI: Kaizen Recommendations ────────────────────────────────────────────────
def get_kaizen_recs(oee, losses, notes, line_name):
    client = get_groq_client()

    top_losses = losses[:3] if losses else []
    loss_text  = "\n".join([f"  - {l['loss']} ({l['type']}): {l['minutes']} mins lost, {l['pct']}% of planned time"
                             for l in top_losses]) or "  - No specific losses quantified"

    prompt = f"""You are a Lean Manufacturing expert specialising in Toyota Production System, OEE optimisation, and Kaizen methodology for automotive battery manufacturing.

Production Line: {line_name}
Shift OEE Results:
  - OEE:          {oee['oee']:.1%}
  - Availability: {oee['availability']:.1%}
  - Performance:  {oee['performance']:.1%}
  - Quality:      {oee['quality']:.1%}
  - Total Units:  {oee['total_count']}
  - Defects:      {oee['defects']}

Six Big Losses (top):
{loss_text}

Shift Notes from Supervisor:
{notes if notes.strip() else "No additional notes provided."}

World-class OEE benchmark: 85%. Current gap: {max(0, 0.85 - oee['oee']):.1%}

Generate exactly 3 prioritised Kaizen opportunities using DMAIC thinking.
Respond ONLY with valid JSON, no markdown, no preamble:
{{
  "opportunities": [
    {{
      "rank": 1,
      "title": "short action title",
      "loss_category": "Downtime|Speed|Quality",
      "problem": "one sentence problem statement",
      "root_cause": "likely root cause via 5-Why",
      "action": "specific Kaizen action to take this week",
      "oee_gain": "estimated % OEE improvement",
      "effort": "Low|Medium|High",
      "weeks": "number of weeks to implement"
    }}
  ]
}}"""

    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = resp.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


# ── AI: Handover Report ───────────────────────────────────────────────────────
def get_handover_report(shift_meta, oee, losses, kaizen, notes):
    client = get_groq_client()

    top_issue   = losses[0]["loss"]  if losses  else "None identified"
    top_kaizen  = kaizen["opportunities"][0]["title"] if kaizen else "Pending analysis"

    prompt = f"""Write a concise, professional shift handover report for a Tesla battery pack production supervisor.
Format it for an incoming shift manager who needs to act fast.

Shift: {shift_meta['shift']} | Line: {shift_meta['line']} | Date: {shift_meta['date']}
Supervisor: {shift_meta['supervisor']}

OEE: {oee['oee']:.1%} (A:{oee['availability']:.1%} P:{oee['performance']:.1%} Q:{oee['quality']:.1%})
Units produced: {oee['good_count']} good / {oee['total_count']} total | Defects: {oee['defects']}
Biggest loss: {top_issue}
Priority Kaizen: {top_kaizen}
Supervisor notes: {notes if notes.strip() else 'None'}

Write using these exact sections with NO markdown headers, just plain text:
SHIFT SUMMARY
(2-3 sentences on overall shift performance)

CRITICAL ISSUES FOR INCOMING SHIFT
(bullet list of max 4 items the next supervisor must address immediately)

EQUIPMENT STATUS
(one sentence per piece of critical equipment - status and any known issues)

TOP PRIORITY ACTION
(one clear sentence — the single most important thing the next shift must do)

Keep total under 220 words. Direct, no fluff, military-style brevity."""

    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# ── UI ────────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

# Header
st.markdown("""
<div style='padding:24px 0 8px'>
  <span style='font-size:28px;font-weight:700;color:#f9fafb;'>🏭 GembaIQ</span>
  <span style='font-size:14px;color:#6b7280;margin-left:12px;'>OEE · Kaizen · Handover · Tesla Battery Production</span>
</div>
""", unsafe_allow_html=True)

# ── Sidebar: Shift Meta ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<div class='section-header'>Shift Info</div>", unsafe_allow_html=True)
    line_name  = st.text_input("Production Line", value="Battery Pack – Line 4")
    supervisor = st.text_input("Supervisor Name",  value="")
    shift_sel  = st.selectbox("Shift", ["Day (06:00–18:00)", "Night (18:00–06:00)"])
    shift_date = st.date_input("Date", value=datetime.today())

    st.markdown("<div class='section-header' style='margin-top:20px'>Planned Time</div>", unsafe_allow_html=True)
    planned_hrs = st.number_input("Planned Production Hours", 1.0, 24.0, 10.0, 0.5)
    planned_mins = planned_hrs * 60

    st.markdown("<div class='section-header' style='margin-top:20px'>Research Basis</div>", unsafe_allow_html=True)
    st.markdown("""
<div style='font-size:11px;color:#6b7280;line-height:1.6'>
OEE methodology: <b>Nakajima (1988)</b> — TPM inventor<br>
Six Big Losses: <b>Toyota Production System</b><br>
Kaizen + OEE gains: <b>9–29% improvement</b><br>
(PMC 2024, ResearchGate 2021)<br>
DMAIC framework: <b>Lean Six Sigma</b><br>
LSS 4.0 + AI: <b>IJML 2025</b>
</div>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊  OEE Calculator", "🔧  Kaizen Priorities", "📋  Handover Report"])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — OEE
# ════════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("<div class='section-header'>Production Data — This Shift</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**⬇ Downtime Losses**")
        unplanned_down = st.number_input("Unplanned Downtime (mins)", 0, int(planned_mins), 0)
        breakdown_mins = st.number_input("  → Equipment Breakdown (mins)", 0, int(planned_mins), 0)
        planned_down   = st.number_input("Planned Downtime / Changeover (mins)", 0, int(planned_mins), 0)
        setup_mins     = st.number_input("  → Setup & Adjustment (mins)", 0, int(planned_mins), 0)

    with c2:
        st.markdown("**⚡ Speed Losses**")
        ideal_cycle_secs = st.number_input("Ideal Cycle Time (seconds/unit)", 1, 3600, 90)
        total_count      = st.number_input("Total Units Produced", 0, 100000, 380)
        minor_stop_mins  = st.number_input("Minor Stops & Idling (mins)", 0, int(planned_mins), 0)
        speed_loss_pct   = st.number_input("Speed Loss vs Ideal (%)", 0.0, 100.0, 0.0, 0.5)

    with c3:
        st.markdown("**✅ Quality Losses**")
        good_count      = st.number_input("Good Units (passed QA)", 0, 100000, 370)
        defect_count    = total_count - good_count
        startup_defects = st.number_input("Startup / First-Off Defects", 0, 1000, 0)
        st.markdown(f"**Defects this shift:** `{defect_count}`")
        notes = st.text_area("Supervisor Notes", placeholder="Describe any issues, near-misses, equipment status…", height=100)

    st.markdown("<br>", unsafe_allow_html=True)
    calc_btn = st.button("Calculate OEE & Identify Losses →")

    if calc_btn:
        if good_count > total_count:
            st.error("Good units cannot exceed total units.")
        elif total_count == 0:
            st.error("Total units produced cannot be zero.")
        else:
            oee = calculate_oee(planned_mins, unplanned_down, planned_down,
                                ideal_cycle_secs, total_count, good_count)
            losses = get_six_losses(oee, breakdown_mins, setup_mins,
                                    minor_stop_mins, speed_loss_pct,
                                    total_count - good_count, startup_defects)

            st.session_state["oee"]    = oee
            st.session_state["losses"] = losses
            st.session_state["notes"]  = notes
            st.session_state["shift_meta"] = {
                "line": line_name, "supervisor": supervisor,
                "shift": shift_sel, "date": str(shift_date)
            }

            # ── OEE Score Banner ──────────────────────────────────────────────
            oee_val = oee["oee"]
            if   oee_val >= 0.85: cls, label = "oee-world-class", "World-Class ✦"
            elif oee_val >= 0.70: cls, label = "oee-good",        "Good"
            elif oee_val >= 0.50: cls, label = "oee-typical",     "Typical"
            else:                 cls, label = "oee-poor",         "Below Target ⚠"

            st.markdown(f"""
<div class='metric-card' style='margin-bottom:20px'>
  <div class='metric-label'>Overall OEE — {label}</div>
  <div class='metric-value {cls}'>{oee_val:.1%}</div>
  <div class='metric-sub'>World-class benchmark: 85% &nbsp;|&nbsp; Gap: {max(0, 0.85-oee_val):.1%}</div>
</div>""", unsafe_allow_html=True)

            # ── Three Gauges ──────────────────────────────────────────────────
            g1, g2, g3 = st.columns(3)
            g1.plotly_chart(oee_gauge(oee["availability"], "Availability"), use_container_width=True)
            g2.plotly_chart(oee_gauge(oee["performance"],  "Performance"),  use_container_width=True)
            g3.plotly_chart(oee_gauge(oee["quality"],      "Quality"),      use_container_width=True)

            # ── Key Stats ─────────────────────────────────────────────────────
            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(f"<div class='metric-card'><div class='metric-label'>Good Units</div><div class='metric-value'>{good_count:,}</div></div>", unsafe_allow_html=True)
            m2.markdown(f"<div class='metric-card'><div class='metric-label'>Defects</div><div class='metric-value oee-poor'>{defect_count:,}</div></div>", unsafe_allow_html=True)
            m3.markdown(f"<div class='metric-card'><div class='metric-label'>Operating Time</div><div class='metric-value'>{oee['operating_time']:.0f}m</div></div>", unsafe_allow_html=True)
            m4.markdown(f"<div class='metric-card'><div class='metric-label'>First Pass Yield</div><div class='metric-value'>{oee['quality']:.1%}</div></div>", unsafe_allow_html=True)

            # ── Six Big Losses Chart ──────────────────────────────────────────
            if losses:
                st.markdown("<br><div class='section-header'>Six Big Losses — This Shift</div>", unsafe_allow_html=True)
                color_map = {"Downtime": "#ef4444", "Speed": "#f59e0b", "Quality": "#3b82f6"}
                df = pd.DataFrame(losses)
                fig = px.bar(df, x="minutes", y="loss", orientation="h",
                             color="type", color_discrete_map=color_map,
                             labels={"minutes": "Minutes Lost", "loss": "", "type": "Loss Type"},
                             template="plotly_dark")
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#1a1d27",
                    height=280, margin=dict(t=10, b=10, l=10, r=10),
                    font=dict(family="Inter", color="#9ca3af"),
                    legend=dict(bgcolor="rgba(0,0,0,0)")
                )
                fig.update_traces(marker_line_width=0)
                st.plotly_chart(fig, use_container_width=True)

            st.success("✅ OEE calculated. Go to **Kaizen Priorities** tab to get AI recommendations.")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — Kaizen
# ════════════════════════════════════════════════════════════════════════════════
with tab2:
    if "oee" not in st.session_state:
        st.info("👈 Calculate OEE first in the **OEE Calculator** tab.")
    else:
        oee    = st.session_state["oee"]
        losses = st.session_state["losses"]
        notes  = st.session_state["notes"]

        st.markdown(f"""
<div style='display:flex;gap:16px;margin-bottom:20px'>
  <div class='metric-card' style='flex:1'><div class='metric-label'>OEE</div><div class='metric-value'>{oee['oee']:.1%}</div></div>
  <div class='metric-card' style='flex:1'><div class='metric-label'>Availability</div><div class='metric-value'>{oee['availability']:.1%}</div></div>
  <div class='metric-card' style='flex:1'><div class='metric-label'>Performance</div><div class='metric-value'>{oee['performance']:.1%}</div></div>
  <div class='metric-card' style='flex:1'><div class='metric-label'>Quality</div><div class='metric-value'>{oee['quality']:.1%}</div></div>
</div>""", unsafe_allow_html=True)

        kai_btn = st.button("Generate Kaizen Recommendations (AI) →")

        if kai_btn or "kaizen" in st.session_state:
            if kai_btn:
                with st.spinner("Analysing losses and generating Kaizen opportunities…"):
                    try:
                        kaizen = get_kaizen_recs(oee, losses, notes, line_name)
                        st.session_state["kaizen"] = kaizen
                    except Exception as e:
                        st.error(f"API error: {e}")
                        kaizen = None
            else:
                kaizen = st.session_state.get("kaizen")

            if kaizen:
                st.markdown("<div class='section-header'>Top 3 Kaizen Opportunities — Prioritised by OEE Impact</div>", unsafe_allow_html=True)
                badge_css = {"Downtime": "loss-badge-downtime", "Speed": "loss-badge-speed", "Quality": "loss-badge-quality"}

                for op in kaizen.get("opportunities", []):
                    bc = badge_css.get(op.get("loss_category", ""), "loss-badge-quality")
                    st.markdown(f"""
<div class='kaizen-card'>
  <span class='kaizen-rank'>#{op['rank']}</span>
  <span class='{bc}' style='margin-left:8px'>{op.get('loss_category','')}</span>
  <div class='kaizen-title'>{op['title']}</div>
  <div style='font-size:13px;color:#d1d5db;margin-bottom:6px'><b>Problem:</b> {op['problem']}</div>
  <div style='font-size:13px;color:#d1d5db;margin-bottom:6px'><b>Root Cause (5-Why):</b> {op['root_cause']}</div>
  <div style='font-size:13px;color:#a5b4fc;margin-bottom:10px'><b>Kaizen Action:</b> {op['action']}</div>
  <div class='kaizen-row'>
    <span class='kaizen-pill'>📈 OEE Gain: {op['oee_gain']}</span>
    <span class='kaizen-pill'>⚡ Effort: {op['effort']}</span>
    <span class='kaizen-pill'>📅 {op['weeks']} weeks</span>
  </div>
</div>""", unsafe_allow_html=True)

                st.markdown("""
<div style='font-size:11px;color:#4b5563;margin-top:16px;padding:12px;background:#0d0f18;border-radius:8px;border:1px solid #1f2937'>
📚 <b>Research basis:</b> Kaizen + OEE analysis improves OEE by 9–29% (PMC 2024). DMAIC methodology 
(Lean Six Sigma). Six Big Losses framework — Toyota Production System. LSS 4.0 AI integration — IJML 2025.
</div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — Handover
# ════════════════════════════════════════════════════════════════════════════════
with tab3:
    if "oee" not in st.session_state:
        st.info("👈 Calculate OEE first in the **OEE Calculator** tab.")
    elif "kaizen" not in st.session_state:
        st.info("👈 Generate Kaizen recommendations first in the **Kaizen Priorities** tab.")
    else:
        oee        = st.session_state["oee"]
        losses     = st.session_state["losses"]
        kaizen     = st.session_state["kaizen"]
        notes      = st.session_state["notes"]
        shift_meta = st.session_state["shift_meta"]

        st.markdown(f"""
<div class='metric-card' style='margin-bottom:20px;text-align:left'>
  <div style='font-size:13px;color:#6b7280'>{shift_meta['line']} &nbsp;·&nbsp; {shift_meta['shift']} &nbsp;·&nbsp; {shift_meta['date']} &nbsp;·&nbsp; Supervisor: {shift_meta['supervisor'] or 'N/A'}</div>
  <div style='font-size:18px;font-weight:600;color:#f9fafb;margin-top:6px'>OEE: {oee['oee']:.1%} &nbsp; | &nbsp; Good Units: {oee['good_count']:,} &nbsp; | &nbsp; Defects: {oee['defects']:,}</div>
</div>""", unsafe_allow_html=True)

        hand_btn = st.button("Generate Shift Handover Report (AI) →")

        if hand_btn or "handover" in st.session_state:
            if hand_btn:
                with st.spinner("Generating handover report…"):
                    try:
                        report = get_handover_report(shift_meta, oee, losses, kaizen, notes)
                        st.session_state["handover"] = report
                    except Exception as e:
                        st.error(f"API error: {e}")
                        report = None
            else:
                report = st.session_state.get("handover")

            if report:
                st.markdown("<div class='section-header'>Shift Handover Report</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='handover-box'>{report}</div>", unsafe_allow_html=True)
                st.code(report, language=None)
                st.caption("↑ Copy the text above to paste into your shift log or email to the incoming supervisor.")
