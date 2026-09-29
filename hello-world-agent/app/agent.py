# ruff: noqa
# Copyright 2026 Google LLC

import json
from typing import Dict, Any, List, Optional
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from .flight_data import MOCK_FLIGHTS, MOCK_GATES
from .a2ui_utils import a2ui_callback
from .live_flights import (
    fetch_live_flights_from_opensky,
    haversine_distance_and_bearing,
    get_heading_arrow,
    render_radar_scope,
    SFO_LAT,
    SFO_LON,
)
from .maps_tools import (
    geocode_address,
    find_nearby_places,
    generate_airplane_static_map_url,
)
from .composite_card import generate_flight_map_card_with_banana
from .aviationstack import (
    get_aviationstack_flight_details,
    list_aviationstack_airport_flights,
)
from .image_tool import generate_dispatch_visual_map
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog

MODEL = "gemini-3.6-flash"


def list_flights() -> str:
    """Lists all current tracked flights at the airport with their basic status, origin, and assigned gate.

    Returns:
        JSON string containing the list of all active flights.
    """
    summary = []
    for fn, f in MOCK_FLIGHTS.items():
        summary.append({
            "flight_number": fn,
            "airline": f["airline"],
            "route": f"{f['origin']} -> {f['destination']}",
            "status": f["status"],
            "gate": f["gate"],
            "est_arrival": f["estimated_arrival"],
            "delay_mins": f["inbound_delay_minutes"],
        })
    return json.dumps(summary, indent=2)


def get_flight_details(flight_number: str) -> str:
    """Retrieves full telemetry, aircraft state, and turnaround details for a specific flight.

    Args:
        flight_number: The flight designator code (e.g., 'UA240', 'DL882', 'AA1054', 'BA287').

    Returns:
        JSON string of detailed flight telemetry and aircraft state, or an error if not found.
    """
    key = flight_number.strip().upper()
    if key in MOCK_FLIGHTS:
        return json.dumps(MOCK_FLIGHTS[key], indent=2)
    return f"Flight '{flight_number}' not found. Available flights: {', '.join(MOCK_FLIGHTS.keys())}"


def calculate_turnaround_delay(
    flight_number: str,
    passenger_deplane_mins: int = 15,
    cleaning_mins: int = 20,
    refueling_mins: int = 15,
    boarding_mins: int = 20,
) -> str:
    """Calculates the expected outbound departure delay based on turnaround operations.

    Args:
        flight_number: The flight designator code (e.g., 'UA240').
        passenger_deplane_mins: Minutes required for deplaning passengers.
        cleaning_mins: Minutes required for cabin cleaning.
        refueling_mins: Minutes required for aircraft refueling.
        boarding_mins: Minutes required for boarding the next flight.

    Returns:
        JSON string detailing turnaround breakdown and projected outbound departure time.
    """
    key = flight_number.strip().upper()
    flight = MOCK_FLIGHTS.get(key)
    if not flight:
        return f"Flight '{flight_number}' not found."

    inbound_delay = flight.get("inbound_delay_minutes", 0)
    critical_path_mins = max(
        passenger_deplane_mins + cleaning_mins + boarding_mins,
        passenger_deplane_mins + refueling_mins + boarding_mins,
    )

    scheduled_turn_buffer = 45
    net_delay = max(0, inbound_delay + critical_path_mins - scheduled_turn_buffer)

    return json.dumps({
        "flight_number": key,
        "inbound_delay_mins": inbound_delay,
        "turnaround_duration_mins": critical_path_mins,
        "scheduled_buffer_mins": scheduled_turn_buffer,
        "projected_outbound_delay_mins": net_delay,
        "on_time_risk": "HIGH" if net_delay > 30 else ("MEDIUM" if net_delay > 0 else "LOW"),
    }, indent=2)


def render_airport_map(highlight_gate: Optional[str] = None) -> str:
    """Renders an ASCII terminal map of SFO showing concourses, gate statuses, and aircraft positions.

    Args:
        highlight_gate: Optional gate to highlight on the map (e.g., 'B4', 'F12', 'G92').

    Returns:
        A formatted string representation of the SFO terminal layout with gate status indicators.
    """
    occupied_gates = {f["gate"]: f for f in MOCK_FLIGHTS.values() if f.get("gate")}

    def gate_symbol(gate_id: str) -> str:
        marker = f"[{gate_id}]"
        if highlight_gate and gate_id.upper() == highlight_gate.upper():
            return f"*{marker}*"
        if gate_id in occupied_gates:
            return f"{marker}(OCC)"
        return f"{marker}(FREE)"

    map_lines = [
        "===========================================================",
        "           SAN FRANCISCO INTERNATIONAL AIRPORT (SFO)       ",
        "                   OPERATIONS RAMP MAP                     ",
        "===========================================================",
        "                                                           ",
        "                   --- RUNWAY 28L / 28R ---                ",
        "  -------------------------------------------------------  ",
        "                                                           ",
        "   TERMINAL 1 (Harvey Milk)         TERMINAL 2             ",
        f"   Gate B1: {gate_symbol('B1')}             Gate C2: {gate_symbol('C2')}",
        f"   Gate B4: {gate_symbol('B4')}             Gate D5: {gate_symbol('D5')}",
        "                                                           ",
        "   TERMINAL 3 (United Hub)          INTERNATIONAL A & G    ",
        f"   Gate F10: {gate_symbol('F10')}           Gate A6: {gate_symbol('A6')}",
        f"   Gate F12: {gate_symbol('F12')}           Gate G92: {gate_symbol('G92')}",
        "                                                           ",
        "  -------------------------------------------------------  ",
        "                   --- RUNWAY 01L / 01R ---                ",
        "===========================================================",
    ]
    return "\n".join(map_lines)


def render_flight_map(flight_number: str) -> str:
    """Renders a flight approach map and status view for a specific flight approaching SFO.

    Args:
        flight_number: The flight designator code (e.g., 'UA240', 'DL882', 'AA1054', 'BA287').

    Returns:
        A formatted string visual of the flight's position relative to SFO with approach telemetry.
    """
    key = flight_number.strip().upper()
    flight = MOCK_FLIGHTS.get(key)
    if not flight:
        return f"Flight '{flight_number}' not found."

    alt = flight["altitude_ft"]
    speed = flight["speed_knots"]
    heading = flight["heading_deg"]
    origin = flight["origin"]
    gate = flight["gate"]
    status = flight["status"]
    delay = flight["inbound_delay_minutes"]

    total_dist = 50
    rem_dist = max(5, int((alt / 35000) * total_dist))
    traveled = max(0, total_dist - rem_dist)

    progress_bar = f"{origin} [" + "=" * (traveled // 2) + ">" + " " * (rem_dist // 2) + "] SFO"

    lines = [
        "===========================================================",
        f"         FLIGHT APPROACH DISPLAY: {key} ({flight['airline']})",
        "===========================================================",
        f" Route:      {origin} -> SFO",
        f" Assigned:   Gate {gate}  |  Status: {status}  |  Delay: {delay} min",
        "-----------------------------------------------------------",
        f" Altitude:   {alt:,} FT",
        f" Speed:      {speed} KTS",
        f" Heading:    {heading}°",
        "-----------------------------------------------------------",
        " Approach Progress:",
        f" {progress_bar}",
        "                                                           ",
        "     [NORDIC FIX] ------> (POINT REYES) ------> [SFO 28R]   ",
        "                              |                            ",
        f"                              +-- [✈ {key}: {alt}ft]      ",
        "===========================================================",
    ]
    return "\n".join(lines)


def list_live_air_traffic(airport_iata: str = "SFO") -> str:
    """Fetches real-time commercial and cargo flights currently active within the Bay Area airspace.

    Returns:
        JSON string containing active flights with callsign, transponder hex, coordinates, altitude,
        speed, heading, distance, and bearing from SFO.
    """
    flights = fetch_live_flights_from_opensky()
    if not flights:
        return json.dumps({
            "status": "NOTICE",
            "message": "No live ADS-B flights currently detected in immediate SFO sector. Checking scheduled flights.",
            "tracked_count": 0,
        })

    flight_summaries = []
    for f in flights:
        alt_ft = round(f["baro_altitude_m"] * 3.28084) if f.get("baro_altitude_m") else None
        speed_kts = round(f["velocity_mps"] * 1.94384) if f.get("velocity_mps") else None
        heading = f.get("true_track_deg")
        arrow = get_heading_arrow(heading)

        dist_nm, bearing_to_target = haversine_distance_and_bearing(
            SFO_LAT, SFO_LON, f["latitude"], f["longitude"]
        )

        flight_summaries.append({
            "callsign": f["callsign"],
            "transponder_icao24": f["icao24"],
            "country": f["origin_country"],
            "altitude_ft": alt_ft,
            "speed_kts": speed_kts,
            "heading_deg": heading,
            "heading_vector": f"{round(heading)}° {arrow}" if heading is not None else "N/A",
            "distance_to_sfo_nm": dist_nm,
            "radial_from_sfo_deg": round(bearing_to_target),
            "coordinates": {"lat": f["latitude"], "lon": f["longitude"]},
        })

    return json.dumps({
        "status": "SUCCESS",
        "reference_airport": airport_iata.upper(),
        "live_aircraft_count": len(flight_summaries),
        "flights": flight_summaries,
    }, indent=2)


def query_live_flight_radar(callsign: str) -> str:
    """Finds a specific live flight by callsign or aircraft transponder hex in Bay Area airspace.

    Args:
        callsign: The aircraft callsign, flight number, or 6-character Mode S hex.

    Returns:
        JSON string containing the matched aircraft's telemetry and distance vector to SFO.
    """
    target = callsign.strip().upper()
    flights = fetch_live_flights_from_opensky()

    matched = None
    for f in flights:
        if target in f["callsign"].upper() or target == f["icao24"].upper():
            matched = f
            break

    if not matched:
        return json.dumps({
            "status": "NOT_FOUND",
            "query": target,
            "message": f"Aircraft '{target}' not currently in Bay Area airspace. Try another flight or use AviationStack.",
        })

    alt_ft = round(matched["baro_altitude_m"] * 3.28084) if matched.get("baro_altitude_m") else None
    speed_kts = round(matched["velocity_mps"] * 1.94384) if matched.get("velocity_mps") else None
    heading = matched.get("true_track_deg")
    arrow = get_heading_arrow(heading)

    dist_nm, bearing = haversine_distance_and_bearing(
        SFO_LAT, SFO_LON, matched["latitude"], matched["longitude"]
    )

    return json.dumps({
        "status": "FOUND",
        "callsign": matched["callsign"],
        "transponder_icao24": matched["icao24"],
        "altitude_ft": alt_ft,
        "speed_kts": speed_kts,
        "heading_vector": f"{round(heading)}° {arrow}" if heading is not None else "N/A",
        "distance_to_sfo_nm": dist_nm,
        "radial_bearing_deg": round(bearing),
        "latitude": matched["latitude"],
        "longitude": matched["longitude"],
    }, indent=2)


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

INSTRUCTION = schema_manager.generate_system_prompt(
    role_description=(
        "You are the SFO Airport Operations & Flight Dispatch Assistant (AeroOps). "
        "You assist airport ground staff, station managers, and ramp dispatchers with live flight monitoring, "
        "gate assignments, aircraft turnaround status, delay forecasts, and real-time AviationStack flight & aircraft data."
    ),
    workflow_description=(
        "Analyze the user request and provide either clean formatted text or a rich visual card depending on what is requested:\n\n"
        "1. DUAL OUTPUT MODES (TEXT vs. IMAGE):\n"
        "   - WHEN USER ASKS FOR TEXT, DETAILS, OR INFORMATION (e.g. 'show flight details as text', 'what is the delay', 'give me info on UA240', 'status of N552DT as text'):\n"
        "     Call get_aviationstack_flight_details(query=...). Output a comprehensive, clearly formatted markdown text summary directly in the chat! "
        "     Include flight status, airline, departure/arrival airports, scheduled vs. actual times, gates, terminals, delays, aircraft tail registration, and model.\n"
        "   - WHEN USER ASKS FOR AN IMAGE, VISUAL CARD, OR MAP (e.g. 'show flight card', 'render flight map', 'generate image', 'show visual card for UA240', 'show card for N552DT'):\n"
        "     Call generate_flight_map_card_with_banana(flight_or_aircraft=...). "
        "     This tool fetches real-time data from AviationStack (and resolves aircraft registrations / transponder hexes), "
        "     dynamically generates the Gemini Nano Banana mascot, embeds Google Maps route imagery, and returns card_image_url.\n"
        "     In your A2UI card output, render an Image component pointing to card_image_url.\n\n"
        "2. AIRCRAFT REGISTRATION & FLIGHT QUERIES:\n"
        "   - You can query by BOTH flight number (e.g. 'UA240', 'DL693', 'CX872') AND aircraft tail registration or Mode S hex (e.g. 'N552DT', 'A70736', 'N77576', 'AB6FDD').\n"
        "   - Both get_aviationstack_flight_details and generate_flight_map_card_with_banana seamlessly support flight numbers and aircraft registrations!\n\n"
        "3. OTHER TOOLS:\n"
        "   - list_aviationstack_airport_flights: lists airport arrivals or departures.\n"
        "   - generate_dispatch_visual_map: generates a standalone high-definition AI image via gemini-3.1-flash-lite-image bound to real flight data.\n"
        "   - geocode_address / find_nearby_places: for address geocoding and nearby amenities."
    ),
    ui_description=(
        "When rendering visual A2UI cards:\n"
        "Keep every surface tiny and flat: ONE Card > ONE Column > one Image (and optional title/caption).\n"
        "Never nest a Card inside a Card.\n"
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use Table, Heading, Buttons, or forms.\n"
        "For flight tracking and status visual cards, display the generated composite card image via the Image component: "
        "{\"Image\": {\"url\": {\"literalString\": \"<card_image_url>\"}}}.\n"
        "Never point an Image at a bare filename, an artifact name, or a non-http(s) path.\n"
        "Output ONLY the raw A2UI JSON array when generating a visual card."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=INSTRUCTION,
    tools=[
        generate_flight_map_card_with_banana,
        get_aviationstack_flight_details,
        list_aviationstack_airport_flights,
        list_flights,
        get_flight_details,
        calculate_turnaround_delay,
        render_airport_map,
        render_flight_map,
        list_live_air_traffic,
        query_live_flight_radar,
        geocode_address,
        find_nearby_places,
        generate_dispatch_visual_map,
    ],
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
