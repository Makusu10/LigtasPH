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
        ]
        for c in centers:
            db.execute("""INSERT INTO evacuation_centers
            (name,address,barangay,city,province,lat,lng,capacity,current_occupancy,food_status,water_status,medicine_status,hygiene_status,basic_needs_status,operational_status,contact_number,notes,archived)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", c)
        # history row example
        db.execute("INSERT INTO center_status_updates (center_id, prev_occupancy, new_occupancy, food_status, water_status, notes, admin_id) VALUES (1, 0, 1200, 'Adequate','Adequate','Initial seed',1)")

    if not db.execute("SELECT 1 FROM emergency_hotlines LIMIT 1").fetchone():
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
        ]
        for h in hotlines:
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
