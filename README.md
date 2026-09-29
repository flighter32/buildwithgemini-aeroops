<div align="center">

# ✈️ AeroOps: Airport Operations & Flight Dispatch Assistant

### An intelligent operations assistant for ground handlers, station managers, and ramp dispatchers — combining real-time flight telemetry, dynamic Google Maps overlays, and generative AI visual dispatch cards.

![AeroOps Demo](assets/demo.gif)

<br/>

![Build with Gemini](https://img.shields.io/badge/Build%20with%20Gemini-World%20Tour-4285F4?logo=google&logoColor=white)
![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Vertex%20AI%20%2B%20Storage-4285F4?logo=googlecloud&logoColor=white)
![Built with ADK](https://img.shields.io/badge/Built%20with-ADK%201.1.0-34A853)
![Python](https://img.shields.io/badge/Python-3.13%2B-blue)
![UI](https://img.shields.io/badge/UI-A2UI%20v0.8%20%2B%20FastAPI-00e5ff)

</div>

---

## 📖 Overview

**AeroOps** is an agentic AI operations assistant built with Google's **Agent Development Kit (ADK)** and **Gemini 3.6 Flash**. Designed for airport operations centers and ground crew teams, AeroOps tracks active commercial flights, verifies aircraft registrations, computes turnaround service buffers, and renders rich visual dispatch cards right inside the dialogue interface.

### What AeroOps Does

- **Live Flight & Airspace Telemetry**: Queries real-time flight details and aircraft registrations (tail numbers / Mode S hex) via the **AviationStack API**, with OpenSky ADS-B vector fallbacks.
- **Visual AI Dispatch Cards**: Generates composite visual flight cards combining live flight metrics, static **Google Maps** route plots, and a custom **Gemini Nano Banana Dispatch Mascot** generated on the fly.
- **Ramp Turnaround & Gate Delay Modeling**: Models service cycles (deplaning, cabin cleaning, fueling, boarding) against gate buffers to calculate turnaround delays and flag on-time departure risks.
- **Geocoding & Ground Amenities**: Resolves ground locations and nearby facilities using the Google Maps Geocoding and Places APIs.
- **Agent-to-User Interface (A2UI)**: Returns clean markdown text or rich display cards through A2UI v0.8 depending on user intent.
- **Tactical ATC / Cockpit Web UI**: Includes a custom dark-mode operations console featuring live UTC clocks, radar telemetry badges, prompt chips, and integrated A2UI card rendering.

---

## 🛠️ Implemented Architecture & Google Cloud Integrations

Based on the codebase in `hello-world-agent/app/`:

| Component / Service | Implementation Details |
|---|---|
| **Core Reasoning Agent** | Powered by `gemini-3.6-flash` on Vertex AI via ADK (`Agent`, `App`, `A2uiSchemaManager`). |
| **Image Generation** | Generates dispatch visuals using `gemini-3.1-flash-lite-image` via the Vertex AI API in the `global` region. |
| **Google Cloud Storage (GCS)** | Public storage bucket for hosting generated flight cards, radar composites, and mascot assets. |
| **A2UI Mini-Renderer** | Custom v0.8 specification catalog integration with dynamic `Image`, `Card`, `Column`, `Row`, and `Text` component surfaces. |
| **Google Maps API** | Static Maps route lines, Geocoding API (`maps_tools.py`), and Places API (New). |
| **AviationStack REST API** | Live flight lookup by flight IATA/ICAO code (e.g. `UA240`, `DL693`) and aircraft registration (e.g. `N552DT`). |
| **ADK Local Artifact Service** | Persists generated flight card artifacts to the ADK session artifact store. |

*(Note on Planned Features: Long-term multi-session Vertex AI Memory Bank and Firestore collections mentioned in earlier planning are planned for future iterations and not wired into the active agent pipeline.)*

---

## 🧰 Available Agent Tools

The agent has the following tools registered in [`app/agent.py`](hello-world-agent/app/agent.py):

1. `generate_flight_map_card_with_banana(flight_or_aircraft)`: Fetches real-time flight/registration data, calls Google Maps Static API for the route, invokes `gemini-3.1-flash-lite-image` for the Nano Banana pilot mascot, composites them onto a dark radar canvas, and publishes it to Cloud Storage.
2. `get_aviationstack_flight_details(query)`: Queries live flight schedule, route, departure/arrival gate, terminal, and aircraft information.
3. `calculate_turnaround_delay(flight_number, gate, scheduled_turnaround_buffer_min)`: Analyzes passenger deplaning, cleaning, fueling, and boarding times against gate buffers.
4. `render_airport_map(highlight_gate)`: Produces an ASCII apron/terminal gate status map for SFO.
5. `render_flight_map(flight_number)`: Renders terminal approach progress and airway fix benchmarks.
6. `list_live_air_traffic(airport_iata)`: Scans live ADS-B vectors, altitudes, ground speeds, and bearings from SFO.
7. `query_live_flight_radar(callsign)`: Locates specific aircraft positions in local airspace.
8. `geocode_address(address)`: Converts street or airport addresses to geographic coordinates via Google Maps.
9. `find_nearby_places(latitude, longitude, place_type, radius_meters)`: Finds nearby amenities, hotels, and fuel depots using Google Places.
10. `generate_dispatch_visual_map(flight_number, gate, prompt_hint)`: Generates a standalone dispatch image with Gemini image generation.

---

## 🚀 Getting Started Locally

### Prerequisites

- Python 3.13+ and [`uv`](https://docs.astral.sh/uv/)
- Google Cloud CLI (`gcloud`) authenticated with a project having Vertex AI enabled
- Google Maps API key with Geocoding, Places, and Maps Static APIs enabled
- AviationStack API key

### 1. Clone & Setup Environment

```bash
git clone https://github.com/flighter32/buildwithgemini-aeroops.git
cd buildwithgemini-aeroops/hello-world-agent

# Configure environment variables in .env
cat <<EOF > .env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
AVIATIONSTACK_API_KEY=your-aviationstack-api-key
PUBLIC_GCS_BUCKET=your-public-gcs-bucket-name
EOF
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Launch the Agent Dev UI

Run the ADK development playground:

```bash
uv run adk web --port 8080 --host 0.0.0.0 --reload_agents
```

Access the ADK playground at port `8080` in your browser.

### 4. Launch the Tactical Frontend Console

In a separate terminal, launch the custom AeroOps operations frontend:

```bash
export LOCAL_ADK_URL="http://127.0.0.1:8080"
export PORT=8081
uv run python -m uvicorn frontend.main:app --host 0.0.0.0 --port 8081
```

Access the AeroOps tactical console at port `8081`.

---

## 💡 Example Queries

- **Live Flight Check (Text)**:
  > *"What is the status and delay for flight UA240 as text?"*
- **Visual AI Flight Card**:
  > *"Where is flight UA240? Show flight map"*
- **Aircraft Tail Search**:
  > *"Inspect aircraft registration N552DT and show flight card"*
- **Gate Turnaround Risk Analysis**:
  > *"Estimate turnaround delay for flight UA240 at Gate B4"*
- **Airspace Overview**:
  > *"Show active flights in the local Bay Area airspace"*

---

## 📄 License

Apache License 2.0. Built for the Google Cloud *Build with Gemini* World Tour.
