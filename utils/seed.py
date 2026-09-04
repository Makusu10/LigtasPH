import json
import sqlite3
from werkzeug.security import generate_password_hash
from flask import current_app
from utils.db import get_db

def seed_db():
    db = get_db()
    # Admin — use app config (already resolved from env with defaults in app.py:24-25)
    admin_user = current_app.config.get("ADMIN_USERNAME", "admin")
    admin_pass = current_app.config.get("ADMIN_PASSWORD", "admin123")
    if not db.execute("SELECT 1 FROM administrators LIMIT 1").fetchone():
        db.execute("INSERT INTO administrators (username, password_hash) VALUES (?,?)",
                   (admin_user, generate_password_hash(admin_pass)))
    # Centers - varied statuses to cover all badges
    if not db.execute("SELECT 1 FROM evacuation_centers LIMIT 1").fetchone():
        centers = [
            ("Marikina Sports Center", "Sumulong Highway, Marikina", "Sto. Niño", "Marikina", "Metro Manila", 14.6308, 121.0968, 5000, 1200, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","(02) 8646-1631", "Demo data - not verified live. Main evacuation hub.", 0),
            ("Quezon City Memorial Circle", "Elliptical Road, Quezon City", "Central", "Quezon City", "Metro Manila", 14.6515, 121.0493, 10000, 3000, "High","Adequate","High","Adequate","High","Open","8925-8417", "Demo data - not verified live.", 0),
            ("Pasig City Sports Center", "Caruncho Ave, Pasig", "San Nicolas", "Pasig", "Metro Manila", 14.5615, 121.0776, 3000, 2800, "Low","Low","Adequate","Low","Low","Open","(02) 8643-0000", "Demo data - Nearly Full (93%).", 0),
            ("Amoranto Sports Complex", "Roces Ave, Quezon City", "Paligsahan", "Quezon City", "Metro Manila", 14.6341, 121.0257, 4000, 3800, "Adequate","High","Adequate","Adequate","Adequate","Open","(02) 8936-1111", "Demo data - Nearly Full (95%).", 0),
            ("Concepcion Integrated School", "Bayabas St, Marikina", "Concepcion Uno", "Marikina", "Metro Manila", 14.6565, 121.1098, 2500, 2500, "Low","Low","Low","Low","Low","Open","(02) 8941-5854", "Demo data - Full capacity.", 0),
            ("San Roque Evacuation Center", "San Roque, Marikina", "San Roque", "Marikina", "Metro Manila", 14.6220, 121.0920, 1500, 400, "High","High","High","High","High","Open","(02) 8646-1631", "Demo data - Available.", 0),
            ("Archived Example Center", "Old Address, Marikina", "Old Barangay", "Marikina", "Metro Manila", 14.6400, 121.1100, 1000, 0, "Unknown","Unknown","Unknown","Unknown","Unknown","Closed","", "Archived demo record.", 1),
            # NCR-wide demo coverage — one hub per remaining LGU so search and
            # the map span the whole province. Contacts intentionally blank:
            # verify with the city DRRMO before relying on any entry.
            ("Manila Evacuation Hub", "Manila City Hall Complex, Manila", "Central", "Manila", "Metro Manila", 14.5995, 120.9842, 6000, 1500, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with Manila DRRMO.", 0),
            ("Makati Evacuation Hub", "Makati City Hall Complex, Makati", "Central", "Makati", "Metro Manila", 14.5547, 121.0244, 3500, 900, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with Makati DRRMO.", 0),
            ("Taguig Evacuation Hub", "Taguig City Hall Complex, Taguig", "Central", "Taguig", "Metro Manila", 14.5176, 121.0509, 4000, 1100, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with Taguig DRRMO.", 0),
            ("Pasay Evacuation Hub", "Pasay City Hall Complex, Pasay", "Central", "Pasay", "Metro Manila", 14.5378, 121.0014, 3000, 700, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with Pasay DRRMO.", 0),
            ("Parañaque Evacuation Hub", "Parañaque City Hall Complex, Parañaque", "Central", "Parañaque", "Metro Manila", 14.4793, 121.0198, 3000, 2700, "Low","Low","Adequate","Low","Low","Open","", "Demo data - Nearly Full (90%). Verify with Parañaque DRRMO.", 0),
            ("Las Piñas Evacuation Hub", "Las Piñas City Hall Complex, Las Piñas", "Central", "Las Piñas", "Metro Manila", 14.4445, 120.9939, 2500, 600, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with Las Piñas DRRMO.", 0),
            ("Muntinlupa Evacuation Hub", "Muntinlupa City Hall Complex, Muntinlupa", "Central", "Muntinlupa", "Metro Manila", 14.4081, 121.0415, 3500, 800, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with Muntinlupa DRRMO.", 0),
            ("Valenzuela Evacuation Hub", "Valenzuela City Hall Complex, Valenzuela", "Central", "Valenzuela", "Metro Manila", 14.7008, 120.9830, 3000, 750, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with Valenzuela DRRMO.", 0),
            ("Caloocan Evacuation Hub", "Caloocan City Hall Complex, Caloocan", "Central", "Caloocan", "Metro Manila", 14.6507, 120.9678, 5000, 1300, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with Caloocan DRRMO.", 0),
            ("Malabon Evacuation Hub", "Malabon City Hall Complex, Malabon", "Central", "Malabon", "Metro Manila", 14.6625, 120.9780, 2000, 500, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with Malabon DRRMO.", 0),
            ("Navotas Evacuation Hub", "Navotas City Hall Complex, Navotas", "Central", "Navotas", "Metro Manila", 14.6667, 120.9417, 2000, 2000, "Low","Low","Low","Low","Low","Open","", "Demo data - Full capacity. Verify with Navotas DRRMO.", 0),
            ("San Juan Evacuation Hub", "San Juan City Hall Complex, San Juan", "Central", "San Juan", "Metro Manila", 14.6019, 121.0355, 1500, 350, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with San Juan DRRMO.", 0),
            ("Mandaluyong Evacuation Hub", "Mandaluyong City Hall Complex, Mandaluyong", "Central", "Mandaluyong", "Metro Manila", 14.5794, 121.0359, 2500, 2100, "Adequate","Low","Adequate","Adequate","Adequate","Open","", "Demo data - Nearly Full (84%). Verify with Mandaluyong DRRMO.", 0),
            ("Pateros Evacuation Hub", "Pateros Municipal Hall Complex, Pateros", "Central", "Pateros", "Metro Manila", 14.5445, 121.0687, 1000, 200, "Adequate","Adequate","Adequate","Adequate","Adequate","Open","", "Demo data - not verified live. Verify with Pateros DRRMO.", 0),
        ]
        for c in centers:
            db.execute("""INSERT INTO evacuation_centers
            (name,address,barangay,city,province,lat,lng,capacity,current_occupancy,food_status,water_status,medicine_status,hygiene_status,basic_needs_status,operational_status,contact_number,notes,archived)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", c)
        # history row example
        db.execute("INSERT INTO center_status_updates (center_id, prev_occupancy, new_occupancy, food_status, water_status, notes, admin_id) VALUES (1, 0, 1200, 'Adequate','Adequate','Initial seed',1)")

    # Emergency hotlines — insert-missing (idempotent) so existing DBs pick
    # up new entries on re-seed. Match key: (agency, contact_number).
    hotlines = [
        ("NDRRMC Marikina Rescue","DRRMO","161","Marikina","","Verified via LGU 2024-12-01","2024-12-01"),
        ("Marikina Police Station","Police","(02) 8646-1631","Marikina","Shoe Ave, Marikina","LGU","2024-11-20"),
        ("QC Disaster Risk Reduction (DRRMO)","DRRMO","122","Quezon City","","LGU","2024-12-02"),
        ("QC Police District","Police","8925-8417","Quezon City","Camp Karingal","PNP","2024-11-15"),
        ("Pasig Emergency Operations","DRRMO","(02) 8643-0000","Pasig","","LGU","2024-12-01"),
        ("Pasig City Police","Police","(02) 8641-0433","Pasig","Pasig Blvd","PNP","2024-11-10"),
        ("National Emergency Hotline","National","911","National","","NDRRMC","2024-01-01"),
        ("Philippine Red Cross","Rescue","143","National","","PRC","2024-01-01"),
        ("PAGASA Weather Hotline","Utility","(02) 8284-0800","National","","PAGASA","2024-01-01"),
        ("Coast Guard Action Center","Rescue","(02) 8527-3877","National","","PCG","2024-01-01"),
        ("BFP Marikina Fire Station","Fire","(02) 8646-0422","Marikina","","BFP","2024-11-25"),
        ("Amang Rodriguez Hospital","Hospital","(02) 8941-5854","Marikina","Sumulong Hwy","DOH","2024-11-20"),
        # Sourced from public directory (disasters2.jimdofree.com/emergency-numbers)
        # on 2026-09-04 — added, not yet independently verified.
        ("PNP Hotline Patrol","Police","117","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("PNP Hotline","Police","722-0650","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("NDRRMC Operations Center","DRRMO","(02) 911-1406","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("OCD – National Capital Region","DRRMO","(02) 421-1918","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("DSWD Disaster Response (text)","Rescue","0918-912-2813","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("Philippine Red Cross Trunkline","Rescue","(02) 527-0000","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("BFP NCR Direct Line","Fire","(02) 426-0219","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("MMDA Rescue Hotline","Rescue","136","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("MMDA Flood Control","Utility","(02) 882-0925","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("PAGASA Weather Forecasting","Utility","(02) 926-4258","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("PHIVOLCS Seismology","Utility","(02) 426-1468","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("DPWH Road Emergency","Utility","165-02","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("Manila Water Hotline","Utility","1627","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("DOTC Public Assistance","Utility","7890","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("Coast Guard Hotline (Globe)","Rescue","0917-724-3682","National","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("Makati C3 Command Center","DRRMO","(02) 870-1940","Makati","","Public directory 2026-09-04, unverified","2026-09-04"),
        ("Mandaluyong Emergency Hotline","DRRMO","(02) 588-2200","Mandaluyong","","Public directory 2026-09-04, unverified","2026-09-04"),
    ]
    # Data fix: early seeds stored the Red Cross trunkline on the PAGASA row.
    # Correct it in existing DBs (fresh DBs get the right number directly).
    db.execute("UPDATE emergency_hotlines SET contact_number='(02) 8284-0800', verification_note='PAGASA', last_verified='2024-01-01' WHERE agency='PAGASA Weather Hotline' AND contact_number='(02) 527-0000'")
    for h in hotlines:
        dup = db.execute("SELECT 1 FROM emergency_hotlines WHERE agency=? AND contact_number=?", (h[0], h[2])).fetchone()
        if not dup:
            db.execute("INSERT INTO emergency_hotlines (agency, category, contact_number, city, address_area, verification_note, last_verified) VALUES (?,?,?,?,?,?,?)", h)

    # weather_cache demo — includes hourly for offline visuals
    if not db.execute("SELECT 1 FROM weather_cache LIMIT 1").fetchone():
        import datetime as _dt
        base = _dt.datetime(2024,12,1,0,0, tzinfo=_dt.timezone.utc)
        hourly_demo = []
        descs = ["Clear sky","Mainly clear","Partly cloudy","Overcast","Light drizzle","Slight rain","Moderate rain"]
        for i in range(24):
            t = base + _dt.timedelta(hours=i)
            code = [0,1,2,3,51,61,63][i % 7]
            hourly_demo.append({"time": t.isoformat(), "temp": 26 + (i%5), "humidity": 78 + (i%10), "wind": round(3.5 + (i%4)*0.8,1), "code": code, "desc": descs[i%7]})
        demo = {"name":"Metro Manila Area","city":"Metro Manila","lat":14.6308,"lon":121.0968,"weather":[{"description":"Scattered clouds","icon":"02d","code":2}],"main":{"temp":27,"humidity":82,"feels_like":31,"temp_max":31,"temp_min":27},"wind":{"speed":4.8},"fetched_at":"2024-12-01T00:00:00Z","_demo":True, "hourly": hourly_demo}
        # attach heat index for demo via same calc
        try:
            from utils.environment import calculate_heat_index, classify_heat_index
            hi = calculate_heat_index(demo["main"]["temp"], demo["main"]["humidity"])
            info = classify_heat_index(hi)
            demo["heat_index"] = {"value_c": hi, "category": info["category"], "color": info["color"], "recommendation": info["recommendation"], "severity": info["severity"], "colors": info["colors"], "method": "Rothfusz (NWS) from temp+humidity"}
        except Exception:
            pass
        db.execute("INSERT INTO weather_cache (city, lat, lng, source, payload) VALUES (?,?,?,?,?)",
                   ("Metro Manila",14.6308,121.0968,"cached", json.dumps(demo)))
    # air-quality demo — offline Good (match image 7.1 µg/m³ PM2.5 • US AQI 50)
    if not db.execute("SELECT 1 FROM weather_cache WHERE source='air-quality' LIMIT 1").fetchone():
        import time as _time
        aq_demo = {"source":"open-meteo-air","scale":"DENR PM2.5 + US EPA AQI (separate)","city":"Metro Manila","lat":14.6308,"lon":121.0968,"aqi":50,"aqi_scale":"US EPA","pm25":7.1,"pm10":14.2,"dominant_pollutant":"PM2.5","category":"Good","color":"green","recommendation":"Air quality is satisfactory. Enjoy outdoor activities.","severity":0,"colors":{"badge":"#ECFDF3","border":"#A6F4C5","text":"#054F31","bar":"#10b981","tint":"rgba(236,253,243,0.45)"},"details":{"carbon_monoxide": 220, "nitrogen_dioxide": 10, "ozone": 42, "sulphur_dioxide": 4},"fetched_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()), "_demo": True}
        db.execute("INSERT INTO weather_cache (city, lat, lng, source, payload) VALUES (?,?,?,?,?)",
                   ("Metro Manila",14.6308,121.0968,"air-quality", json.dumps(aq_demo)))
    db.commit()
