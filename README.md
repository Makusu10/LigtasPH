# Ligtas: Evacuation Center & Disaster Response Management System

**Ligtas** is a centralized web application designed for emergency disaster response and evacuation management. It maps publicly designated evacuation centers, tracks real-time capacities and vital supply inventories (food, water, medical), visualizes flood-prone hazard zones, and provides localized emergency hotlines and proximity-based medical/police facility directories.

---

## 🚀 Quick Start Guide (Run Locally from GitHub)

### Prerequisites

Ensure you have installed on your machine:
- **Node.js**: `v18.0.0` or higher (`v20+` or `v22+` recommended)
- **npm** (comes with Node.js) or **pnpm** / **yarn** / **bun**
- **Git**

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

---

### Step 2: Install Dependencies

```bash
npm install
```

---

### Step 3: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` and fill in your keys (optional for basic local preview):
   ```env
   # Required for AI-assisted emergency triage / disaster features (optional fallback provided)
   GEMINI_API_KEY="your_gemini_api_key_here"

   # OpenWeather API key for live meteorological radar & weather updates (optional fallback provided)
   OPENWEATHER_API_KEY="your_openweather_api_key_here"
   ```

> **Note:** The application includes built-in fallback modes for weather and AI logic, so the app will run locally even without API keys configured immediately.

---

### Step 4: Start the Development Server

```bash
npm run dev
```

The application will start at:
👉 **`http://localhost:3000`**

Open your browser and navigate to `http://localhost:3000`.

---

## 🛠️ Available Scripts

In the project directory, you can run:

| Command | Description |
| :--- | :--- |
| `npm run dev` | Starts the Express + Vite unified development server with TypeScript support on port 3000. |
| `npm run build` | Builds the client-side SPA bundle (`dist/`) and bundles the server entry point (`dist/server.cjs`) using `esbuild`. |
| `npm start` | Runs the production build (`node dist/server.cjs`). Run `npm run build` first. |
| `npm run lint` | Runs the TypeScript compiler (`tsc --noEmit`) to validate type safety. |
| `npm run clean` | Cleans build artifacts (`dist/`). |

---

## 📦 Production Deployment

To test or run in production mode:

```bash
# 1. Build the frontend and backend bundle
npm run build

# 2. Start the production server
npm start
```

---

## 🏗️ Tech Stack & Architecture

- **Frontend**:
  - [React 19](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
  - [Vite 6](https://vitejs.dev/)
  - [Tailwind CSS v4](https://tailwindcss.com/)
  - [React-Leaflet](https://react-leaflet.js.org/) & [Leaflet](https://leafletjs.com/) (Interactive GIS mapping, flood hazard overlays, and GPS positioning)
  - [Lucide React](https://lucide.dev/) (Iconography)
  - [Motion](https://motion.dev/) (Smooth entry & state transitions)
- **Backend & Storage**:
  - [Express](https://expressjs.com/) (Full-stack API & SSR asset proxy)
  - [SQLite / sql.js](https://github.com/sql-js/sql.js) (Database persistence for center capacities and inventory logs)
  - [@google/genai](https://www.npmjs.com/package/@google/genai) (Server-side Gemini AI integration)

---

## 🗺️ Key Features

1. **Interactive Evacuation Center Map**: View real-time capacity percentages, food/water/medical supply statuses, and occupancy indicators.
2. **Flood Hazard Zonation Layer**: High and moderate flood-prone risk zone overlays (e.g., Marikina River basin, Provident Village, Tumana).
3. **Emergency Services Overlay**: Filterable map toggles for Evacuation Centers, Hospitals/Clinics, Police Stations, and Hazard Zones.
4. **Live Geolocation & Recenter**: Visual GPS tracker marking user coordinates with a continuous pulse marker and a one-click recenter button.
5. **Local Emergency Hub**: Geodesic distance calculation to nearest medical facilities with one-tap emergency calling and Google Maps directions.
6. **Supply Management Panel**: Real-time supply tracking and status updates.
