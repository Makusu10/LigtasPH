"""Shared environmental classification utilities — PAGASA Heat Index + DENR PM2.5 + US EPA AQI.

Heat Index: NWS Rothfusz regression (F) -> C, with low/high humidity adjustments.
Thresholds per spec (Celsius). AQI helpers keep DENR PM2.5 µg/m³ separate from US AQI numeric.
"""
import math

# PAGASA Heat Index categories (Celsius)
# Below 27: Not Hazardous | 27-32 Caution | 33-41 Extreme Caution | 42-51 Danger | >=52 Extreme Danger
HEAT_CATEGORIES = [
    (27, "Not Hazardous", "green", "Normal outdoor precautions are advised."),
    (33, "Caution", "yellow", "Fatigue may occur with prolonged exposure."),
    (42, "Extreme Caution", "orange", "Limit prolonged outdoor activity and drink water regularly."),
    (52, "Danger", "red-orange", "Avoid strenuous outdoor activity and watch for signs of heat illness."),
    (float("inf"), "Extreme Danger", "dark-red", "Stay indoors when possible and seek help if symptoms occur."),
]

# Color mapping for heat — used for badge/bar/card tint (avoid full-page red, use subtle gradient)
HEAT_COLORS = {
    "Not Hazardous": {"badge": "#ECFDF3", "border": "#A6F4C5", "text": "#054F31", "bar": "#10b981", "tint": "rgba(236,253,243,0.45)"},
    "Caution": {"badge": "#FEF9C3", "border": "#FDE68A", "text": "#854D0E", "bar": "#eab308", "tint": "rgba(254,249,195,0.45)"},
    "Extreme Caution": {"badge": "#FFEDD5", "border": "#FDBA74", "text": "#7C2D12", "bar": "#f97316", "tint": "rgba(255,237,213,0.55)"},
    "Danger": {"badge": "#FEE2E2", "border": "#FCA5A5", "text": "#7F1D1D", "bar": "#ef4444", "tint": "rgba(254,226,226,0.55)"},
    "Extreme Danger": {"badge": "#450A0A", "border": "#7F1D1D", "text": "#FEF2F2", "bar": "#7f1d1d", "tint": "rgba(127,29,29,0.12)"},
}

# DENR PM2.5 (µg/m³) — DAO 2020-14
DENR_PM25 = [
    (25, "Good", "green", "Air quality is satisfactory. Enjoy outdoor activities."),
    (35, "Fair", "yellow", "Air quality is acceptable. Sensitive individuals should watch for symptoms."),
    (45, "Unhealthy for Sensitive Groups", "orange", "Sensitive groups should limit prolonged outdoor exertion."),
    (55, "Very Unhealthy", "red", "Everyone should avoid prolonged outdoor exertion."),
    (90, "Acutely Unhealthy", "purple", "Avoid outdoor activity. Sensitive groups should stay indoors."),
    (float("inf"), "Emergency", "maroon", "Stay indoors and keep activity levels low."),
]
DENR_COLORS = {
    "Good": {"badge": "#ECFDF3", "border": "#A6F4C5", "text": "#054F31", "bar": "#10b981", "tint": "rgba(236,253,243,0.45)"},
    "Fair": {"badge": "#FEF9C3", "border": "#FDE68A", "text": "#854D0E", "bar": "#eab308", "tint": "rgba(254,249,195,0.45)"},
    "Unhealthy for Sensitive Groups": {"badge": "#FFEDD5", "border": "#FDBA74", "text": "#7C2D12", "bar": "#f97316", "tint": "rgba(255,237,213,0.55)"},
    "Very Unhealthy": {"badge": "#FEE2E2", "border": "#FCA5A5", "text": "#7F1D1D", "bar": "#ef4444", "tint": "rgba(254,226,226,0.55)"},
    "Acutely Unhealthy": {"badge": "#F3E8FF", "border": "#D8B4FE", "text": "#581C87", "bar": "#9333ea", "tint": "rgba(243,232,255,0.55)"},
    "Emergency": {"badge": "#450A0A", "border": "#7F1D1D", "text": "#FEF2F2", "bar": "#7f1d1d", "tint": "rgba(127,29,29,0.12)"},
}

# Severity ordering for overall risk (more severe wins)
HEAT_SEVERITY = {"Not Hazardous": 0, "Caution": 1, "Extreme Caution": 2, "Danger": 3, "Extreme Danger": 4}
AQI_SEVERITY = {"Good": 0, "Fair": 1, "Unhealthy for Sensitive Groups": 2, "Very Unhealthy": 3, "Acutely Unhealthy": 4, "Emergency": 5}

def _c_to_f(c): return c * 9/5 + 32
def _f_to_c(f): return (f - 32) * 5/9

def calculate_heat_index(temp_c, rh):
    """NWS Rothfusz heat index. Returns Celsius. Falls back to temp_c if out of valid range.

    Valid range for full regression: T >= 80F (26.7C) and RH >= 40%. Below that, use simple
    Steadman-like or return temp. We follow NWS guidance: if HI < 80F, return temp.
    """
    if temp_c is None or rh is None:
        return None
    try:
        t = float(temp_c); r = float(rh)
    except Exception:
        return None
    if not (-50 < t < 60 and 0 <= r <= 100):
        return None
    tf = _c_to_f(t)
    # Below 80F, heat index ≈ temperature
    if tf < 80:
        # Use simple formula for low temps: HI = 0.5*(T + 61 + 1.2*(T-68) + 0.094*RH) — but keep as temp for our spec
        return round(t, 1)
    # Rothfusz regression
    hi_f = (-42.379 + 2.04901523*tf + 10.14333127*r - 0.22475541*tf*r
            - 0.00683783*tf*tf - 0.05481717*r*r + 0.00122874*tf*tf*r
            + 0.00085282*tf*r*r - 0.00000199*tf*tf*r*r)
    # Adjustments
    if r < 13 and 80 <= tf <= 112:
        hi_f -= ((13 - r)/4) * math.sqrt((17 - abs(tf - 95))/17)
    elif r > 85 and 80 <= tf <= 87:
        hi_f += ((r - 85)/10) * ((87 - tf)/5)
    # NWS: if HI < 80F, don't report below 80
    if hi_f < 80:
        hi_f = 80
    return round(_f_to_c(hi_f), 1)

def classify_heat_index(hi_c):
    if hi_c is None or (isinstance(hi_c, float) and math.isnan(hi_c)):
        return {"category": "Unavailable", "color": "unknown", "recommendation": "Heat index unavailable — check temperature and humidity.", "severity": -1, "colors": {"badge":"#F9FAFB","border":"#D0D5DD","text":"#667085","bar":"#667085","tint":"rgba(249,250,251,0.6)"}}
    for threshold, cat, color, rec in HEAT_CATEGORIES:
        # spec boundaries inclusive lower: Below 27, 27-32, 33-41, 42-51, 52+
        # Our thresholds: 27,33,42,52,inf — need exact mapping per spec
        # 27 to 32.9 -> Caution, 33 to 41.9 -> Extreme Caution, etc.
        # So we treat: hi <27 -> Not Hazardous, hi <33 -> Caution, hi <42 -> Extreme Caution, hi <52 -> Danger, else Extreme Danger
        if hi_c < threshold:
            # special: first threshold 27 is Not Hazardous for hi<27, Caution is 27<=hi<33
            # Our loop as defined already encodes that via ordered thresholds
            # HEAT_CATEGORIES[0] threshold 27 -> hi<27 Not Hazardous
            # [1] 33 -> hi<33 Caution (covers 27-32)
            # [2] 42 -> hi<42 Extreme Caution (33-41)
            # [3] 52 -> hi<52 Danger (42-51)
            # [4] inf -> Extreme Danger (52+)
            return {"category": cat, "color": color, "recommendation": rec, "severity": HEAT_SEVERITY[cat], "colors": HEAT_COLORS[cat]}
    return {"category": "Extreme Danger", "color": "dark-red", "recommendation": HEAT_CATEGORIES[-1][3], "severity": 4, "colors": HEAT_COLORS["Extreme Danger"]}

def classify_pm25(pm25):
    if pm25 is None or (isinstance(pm25, float) and math.isnan(pm25)):
        return {"category": "Unavailable", "color": "unknown", "recommendation": "Air quality unavailable for this location.", "severity": -1, "colors": {"badge":"#F9FAFB","border":"#D0D5DD","text":"#667085","bar":"#667085","tint":"rgba(249,250,251,0.6)"}}
    try:
        v = float(pm25)
    except Exception:
        return {"category": "Unavailable", "color": "unknown", "recommendation": "Air quality unavailable for this location.", "severity": -1, "colors": {"badge":"#F9FAFB","border":"#D0D5DD","text":"#667085","bar":"#667085","tint":"rgba(249,250,251,0.6)"}}
    # DENR DAO 2020-14 inclusive boundaries as spec: 0-25 Good, 25.1-35 Fair, etc. Use > thresholds with float
    for threshold, cat, color, rec in DENR_PM25:
        if v <= threshold:
            return {"category": cat, "color": color, "recommendation": rec, "severity": AQI_SEVERITY[cat], "colors": DENR_COLORS[cat]}
    return {"category": "Emergency", "color": "maroon", "recommendation": DENR_PM25[-1][3], "severity": 5, "colors": DENR_COLORS["Emergency"]}

def overall_status(heat_cat, aqi_cat):
    """Overall outdoor-safety — more severe wins. Returns {category, color, recommendation, source}."""
    h_sev = HEAT_SEVERITY.get(heat_cat, -1) if heat_cat not in (None, "Unavailable") else -1
    a_sev = AQI_SEVERITY.get(aqi_cat, -1) if aqi_cat not in (None, "Unavailable") else -1
    if h_sev == -1 and a_sev == -1:
        return {"category": "Unavailable", "recommendation": "Environmental data unavailable.", "severity": -1}
    if h_sev >= a_sev:
        # heat drives overall
        rec = next((r for _, c, _, r in HEAT_CATEGORIES if c == heat_cat), "")
        return {"category": heat_cat, "source": "heat", "recommendation": rec, "severity": h_sev}
    else:
        rec = next((r for _, c, _, r in DENR_PM25 if c == aqi_cat), "")
        return {"category": aqi_cat, "source": "air", "recommendation": rec, "severity": a_sev}
