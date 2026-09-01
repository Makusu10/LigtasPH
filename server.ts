import express from "express";
import path from "path";
import fs from "fs";
import cors from "cors";
import jwt from "jsonwebtoken";
import initSqlJs, { Database } from "sql.js";
import { createServer as createViteServer } from "vite";

const SECRET_KEY = process.env.JWT_SECRET || "ligtas-secret-key-123";
const DB_FILE = "ligtas.sqlite";

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());

let db: Database;

function saveDb() {
  if (db) {
    const data = db.export();
    const buffer = Buffer.from(data);
    fs.writeFileSync(DB_FILE, buffer);
  }
}

async function initDatabase() {
  const SQL = await initSqlJs();

  if (fs.existsSync(DB_FILE)) {
    const fileBuffer = fs.readFileSync(DB_FILE);
    db = new SQL.Database(fileBuffer);
  } else {
    db = new SQL.Database();
  }

  // Create tables
  db.run(`CREATE TABLE IF NOT EXISTS centers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    capacity INTEGER NOT NULL,
    currentOccupancy INTEGER DEFAULT 0,
    foodStatus TEXT DEFAULT 'Adequate',
    waterStatus TEXT DEFAULT 'Adequate',
    medicalStatus TEXT DEFAULT 'Adequate'
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS hotlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    agency TEXT NOT NULL,
    number TEXT NOT NULL
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
  )`);

  // Check and seed centers
  const centerRes = db.exec("SELECT COUNT(*) as count FROM centers");
  const centerCount = centerRes.length > 0 && centerRes[0].values.length > 0 ? (centerRes[0].values[0][0] as number) : 0;
  if (centerCount === 0) {
    db.run("INSERT INTO centers (name, city, lat, lng, capacity, currentOccupancy, foodStatus, waterStatus, medicalStatus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
      "Marikina Sports Center", "Marikina", 14.6308, 121.0968, 5000, 1200, "Adequate", "Adequate", "Adequate"
    ]);
    db.run("INSERT INTO centers (name, city, lat, lng, capacity, currentOccupancy, foodStatus, waterStatus, medicalStatus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
      "Quezon City Memorial Circle", "Quezon City", 14.6515, 121.0493, 10000, 3000, "High", "Adequate", "High"
    ]);
    db.run("INSERT INTO centers (name, city, lat, lng, capacity, currentOccupancy, foodStatus, waterStatus, medicalStatus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
      "Pasig City Sports Center", "Pasig", 14.5615, 121.0776, 3000, 2800, "Low", "Low", "Adequate"
    ]);
    db.run("INSERT INTO centers (name, city, lat, lng, capacity, currentOccupancy, foodStatus, waterStatus, medicalStatus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
      "Amoranto Sports Complex", "Quezon City", 14.6341, 121.0257, 4000, 1500, "Adequate", "High", "Adequate"
    ]);
    db.run("INSERT INTO centers (name, city, lat, lng, capacity, currentOccupancy, foodStatus, waterStatus, medicalStatus) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
      "Concepcion Integrated School", "Marikina", 14.6565, 121.1098, 2500, 950, "High", "Adequate", "Adequate"
    ]);
  }

  // Check and seed hotlines
  const hotlineRes = db.exec("SELECT COUNT(*) as count FROM hotlines");
  const hotlineCount = hotlineRes.length > 0 && hotlineRes[0].values.length > 0 ? (hotlineRes[0].values[0][0] as number) : 0;
  if (hotlineCount === 0) {
    db.run("INSERT INTO hotlines (city, agency, number) VALUES (?, ?, ?)", ["Marikina", "NDRRMC Marikina Rescue", "161"]);
    db.run("INSERT INTO hotlines (city, agency, number) VALUES (?, ?, ?)", ["Marikina", "Marikina Police Station", "(02) 8646-1631"]);
    db.run("INSERT INTO hotlines (city, agency, number) VALUES (?, ?, ?)", ["Quezon City", "QC Disaster Risk Reduction (DRRMO)", "122"]);
    db.run("INSERT INTO hotlines (city, agency, number) VALUES (?, ?, ?)", ["Quezon City", "QC Police District", "8925-8417"]);
    db.run("INSERT INTO hotlines (city, agency, number) VALUES (?, ?, ?)", ["Pasig", "Pasig Emergency Operations", "(02) 8643-0000"]);
    db.run("INSERT INTO hotlines (city, agency, number) VALUES (?, ?, ?)", ["Pasig", "Pasig City Police", "(02) 8641-0433"]);
    db.run("INSERT INTO hotlines (city, agency, number) VALUES (?, ?, ?)", ["National", "National Emergency Hotline", "911"]);
    db.run("INSERT INTO hotlines (city, agency, number) VALUES (?, ?, ?)", ["National", "Philippine Red Cross", "143"]);
    db.run("INSERT INTO hotlines (city, agency, number) VALUES (?, ?, ?)", ["National", "PAGASA Weather Hotline", "(02) 8284-0800"]);
    db.run("INSERT INTO hotlines (city, agency, number) VALUES (?, ?, ?)", ["National", "Coast Guard Action Center", "(02) 8527-3877"]);
  }

  // Check and seed admin
  const adminRes = db.exec("SELECT COUNT(*) as count FROM admins");
  const adminCount = adminRes.length > 0 && adminRes[0].values.length > 0 ? (adminRes[0].values[0][0] as number) : 0;
  if (adminCount === 0) {
    db.run("INSERT INTO admins (username, password) VALUES ('admin', 'password')");
  }

  saveDb();
  console.log("SQLite Database initialized and ready.");
}

// Authentication Middleware
const authenticateToken = (req: any, res: any, next: any) => {
  const authHeader = req.headers["authorization"];
  const token = authHeader && authHeader.split(" ")[1];

  if (token == null) return res.sendStatus(401);

  jwt.verify(token, SECRET_KEY, (err: any, user: any) => {
    if (err) return res.sendStatus(403);
    req.user = user;
    next();
  });
};

function formatResults(results: any[]) {
  if (!results || results.length === 0) return [];
  const columns = results[0].columns;
  const values = results[0].values;
  return values.map((row: any[]) => {
    const obj: any = {};
    columns.forEach((col: string, idx: number) => {
      obj[col] = row[idx];
    });
    return obj;
  });
}

// --- API ROUTES ---

// Login
app.post("/api/login", (req, res) => {
  try {
    const { username, password } = req.body;
    const stmt = db.prepare("SELECT * FROM admins WHERE username = :username AND password = :password");
    stmt.bind({ ":username": username, ":password": password });
    
    let userRow: any = null;
    if (stmt.step()) {
      userRow = stmt.getAsObject();
    }
    stmt.free();

    if (!userRow) {
      return res.status(401).json({ error: "Invalid username or password" });
    }

    const token = jwt.sign({ username }, SECRET_KEY, { expiresIn: "4h" });
    res.json({ token });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Get all centers
app.get("/api/centers", (req, res) => {
  try {
    const result = db.exec("SELECT * FROM centers ORDER BY id ASC");
    const rows = formatResults(result);
    res.json(rows);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Update a center (Admin only)
app.put("/api/centers/:id", authenticateToken, (req, res) => {
  try {
    const { currentOccupancy, foodStatus, waterStatus, medicalStatus } = req.body;
    const id = parseInt(req.params.id);

    db.run(
      "UPDATE centers SET currentOccupancy = ?, foodStatus = ?, waterStatus = ?, medicalStatus = ? WHERE id = ?",
      [currentOccupancy, foodStatus, waterStatus, medicalStatus || "Adequate", id]
    );
    saveDb();

    res.json({ message: "Center updated successfully" });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Get hotlines (can filter by city)
app.get("/api/hotlines", (req, res) => {
  try {
    const city = req.query.city as string;
    let result;
    if (city) {
      const stmt = db.prepare("SELECT * FROM hotlines WHERE city = :city OR city = 'National' ORDER BY id ASC");
      stmt.bind({ ":city": city });
      const rows: any[] = [];
      while (stmt.step()) {
        rows.push(stmt.getAsObject());
      }
      stmt.free();
      return res.json(rows);
    } else {
      result = db.exec("SELECT * FROM hotlines ORDER BY id ASC");
      const rows = formatResults(result);
      return res.json(rows);
    }
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// Weather API Proxy
app.get("/api/weather", async (req, res) => {
  const { lat, lon } = req.query;
  const apiKey = process.env.OPENWEATHER_API_KEY;
  
  if (!apiKey || apiKey === "YOUR_OPENWEATHER_API_KEY") {
    // Provide a graceful meteorological fallback if API key is not configured yet
    return res.json({
      name: "Metro Manila Area",
      weather: [{ description: "Scattered Rain Showers", icon: "10d" }],
      main: { temp: 28, humidity: 82, feels_like: 31 },
      wind: { speed: 4.8 }
    });
  }

  try {
    const response = await fetch(
      `https://api.openweathermap.org/data/2.5/weather?lat=${lat || 14.6308}&lon=${lon || 121.0968}&appid=${apiKey}&units=metric`
    );
    if (!response.ok) {
      throw new Error(`OpenWeather API returned ${response.status}`);
    }
    const data = await response.json();
    res.json(data);
  } catch (error: any) {
    // Fallback gracefully on weather fetch error so the dashboard widget stays functional
    res.json({
      name: "Metro Manila Area",
      weather: [{ description: "Moderate Rain", icon: "10d" }],
      main: { temp: 27, humidity: 85, feels_like: 30 },
      wind: { speed: 5.2 }
    });
  }
});

import { CRITICAL_FACILITIES } from './src/data/criticalFacilities';

function calculateDistanceInMeters(lat1: number, lon1: number, lat2: number, lon2: number) {
  const R = 6371e3; // meters
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const deltaP = ((lat2 - lat1) * Math.PI) / 180;
  const deltaL = ((lon2 - lon1) * Math.PI) / 180;

  const a = Math.sin(deltaP / 2) * Math.sin(deltaP / 2) +
            Math.cos(p1) * Math.cos(p2) *
            Math.sin(deltaL / 2) * Math.sin(deltaL / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c;
}

app.get("/api/nearby-health", async (req, res) => {
  const lat = parseFloat(req.query.lat as string);
  const lon = parseFloat(req.query.lon as string);

  const targetLat = !isNaN(lat) ? lat : 14.6308;
  const targetLon = !isNaN(lon) ? lon : 121.0968;

  const healthFacilities = CRITICAL_FACILITIES.filter(f => f.type === 'hospital' || f.type === 'clinic');

  const sorted = healthFacilities.map((facility) => {
    const distMeters = calculateDistanceInMeters(targetLat, targetLon, facility.lat, facility.lon);
    return {
      ...facility,
      distance: Math.round(distMeters)
    };
  }).sort((a, b) => (a.distance || 0) - (b.distance || 0));

  res.json(sorted.slice(0, 5));
});


async function startServer() {
  await initDatabase();

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
