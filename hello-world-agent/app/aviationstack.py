"""AviationStack API client for live flight schedules, airlines, departures, arrivals, and aircraft data.
Supports querying by flight number / callsign (e.g. 'UA240', 'DL693', 'CX872')
and aircraft registration / Mode S transponder hex (e.g. 'N552DT', 'A70736', 'N77576').
"""

import os
import json
import urllib.request
from typing import Dict, Any, List, Optional
import requests

DEFAULT_AVIATIONSTACK_KEY = "a9b53c2fc87db1f69fbf784c1b3c68a2"
BASE_URL = "http://api.aviationstack.com/v1/flights"
CACHE_FILE = "/config/Desktop/BuildWithGemini/hello-world-agent/app/aviationstack_cache.json"


def get_aviationstack_api_key() -> str:
    """Retrieves the AviationStack API key from environment variable or default fallback."""
    return os.environ.get("AVIATIONSTACK_API_KEY", DEFAULT_AVIATIONSTACK_KEY)


def load_cached_flights() -> Dict[str, Any]:
    """Loads previously fetched real AviationStack flight data as a resilient fallback."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_cached_flight(key: str, data: Dict[str, Any]) -> None:
    """Saves live AviationStack responses to local cache."""
    try:
        cache = load_cached_flights()
        cache[key.upper()] = data
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def lookup_aircraft_metadata(reg_or_icao24: str) -> Dict[str, Any]:
    """Looks up registration and ICAO aircraft metadata from hexdb.io."""
    clean = reg_or_icao24.strip().upper()
    url = f"https://hexdb.io/api/v1/aircraft/{clean.lower()}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as res:
            return json.loads(res.read().decode())
    except Exception:
        return {}


def query_aviationstack_flights(
    flight_iata: Optional[str] = None,
    flight_icao: Optional[str] = None,
    dep_iata: Optional[str] = None,
    arr_iata: Optional[str] = None,
    airline_name: Optional[str] = None,
    flight_status: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """Queries real-time flight data from the AviationStack REST API."""
    api_key = get_aviationstack_api_key()
    params: Dict[str, Any] = {
        "access_key": api_key,
        "limit": min(limit, 20),
    }

    if flight_iata:
        params["flight_iata"] = flight_iata.strip().upper()
    elif flight_icao:
        params["flight_icao"] = flight_icao.strip().upper()
    if dep_iata:
        params["dep_iata"] = dep_iata.strip().upper()
    if arr_iata:
        params["arr_iata"] = arr_iata.strip().upper()
    if airline_name:
        params["airline_name"] = airline_name.strip()
    if flight_status:
        params["flight_status"] = flight_status.strip().lower()

    try:
        response = requests.get(BASE_URL, params=params, timeout=8)
        raw_json = response.json()
        
        # Check if rate limit hit
        if response.status_code == 429 or "error" in raw_json:
            error_code = raw_json.get("error", {}).get("code", "")
            # Check local cache for fallback
            cache = load_cached_flights()
            query_key = (flight_iata or flight_icao or "").upper()
            if query_key and query_key in cache:
                return {
                    "status": "SUCCESS",
                    "source": "aviationstack.com (cached data)",
                    "total_results": 1,
                    "flights": [cache[query_key]],
                }
            return {
                "status": "ERROR",
                "error_code": error_code,
                "error": raw_json.get("error", {}).get("message", f"HTTP {response.status_code} error from AviationStack")
            }

        flights_data = raw_json.get("data", [])
        formatted_flights = []

        for item in flights_data:
            dep = item.get("departure") or {}
            arr = item.get("arrival") or {}
            airline = item.get("airline") or {}
            flight = item.get("flight") or {}
            aircraft = item.get("aircraft") or {}
            live = item.get("live") or {}

            icao24 = aircraft.get("icao24")
            reg = aircraft.get("registration")
            model = aircraft.get("iata") or aircraft.get("icao")
            
            if icao24 and not reg:
                meta = lookup_aircraft_metadata(icao24)
                if meta:
                    reg = meta.get("Registration")
                    model = model or meta.get("Type") or meta.get("ICAOTypeCode")

            flight_obj = {
                "flight_date": item.get("flight_date"),
                "flight_status": item.get("flight_status"),
                "airline": {
                    "name": airline.get("name"),
                    "iata": airline.get("iata"),
                    "icao": airline.get("icao"),
                },
                "flight": {
                    "number": flight.get("number"),
                    "iata": flight.get("iata"),
                    "icao": flight.get("icao"),
                    "codeshared": flight.get("codeshared"),
                },
                "departure": {
                    "airport": dep.get("airport"),
                    "timezone": dep.get("timezone"),
                    "iata": dep.get("iata"),
                    "icao": dep.get("icao"),
                    "terminal": dep.get("terminal"),
                    "gate": dep.get("gate"),
                    "delay_minutes": dep.get("delay"),
                    "scheduled": dep.get("scheduled"),
                    "estimated": dep.get("estimated"),
                    "actual": dep.get("actual"),
                    "estimated_runway": dep.get("estimated_runway"),
                    "actual_runway": dep.get("actual_runway"),
                },
                "arrival": {
                    "airport": arr.get("airport"),
                    "timezone": arr.get("timezone"),
                    "iata": arr.get("iata"),
                    "icao": arr.get("icao"),
                    "terminal": arr.get("terminal"),
                    "gate": arr.get("gate"),
                    "baggage_claim": arr.get("baggage"),
                    "delay_minutes": arr.get("delay"),
                    "scheduled": arr.get("scheduled"),
                    "estimated": arr.get("estimated"),
                    "actual": arr.get("actual"),
                    "estimated_runway": arr.get("estimated_runway"),
                    "actual_runway": arr.get("actual_runway"),
                },
                "aircraft": {
                    "registration": reg,
                    "model": model,
                    "iata": aircraft.get("iata"),
                    "icao": aircraft.get("icao"),
                    "icao24": icao24,
                },
                "live": live,
            }
            formatted_flights.append(flight_obj)
            if flight.get("iata"):
                save_cached_flight(flight.get("iata"), flight_obj)

        return {
            "status": "SUCCESS",
            "source": "aviationstack.com",
            "total_results": len(formatted_flights),
            "flights": formatted_flights,
        }

    except Exception as e:
        return {
            "status": "ERROR",
            "error": f"Failed to connect to AviationStack: {str(e)}"
        }


def search_flight_or_aircraft(query: str) -> Dict[str, Any]:
    """Searches AviationStack for a flight by flight number, callsign, or aircraft registration / ICAO24 hex."""
    clean_q = query.strip().upper()

    # 1. Try flight_iata directly
    res = query_aviationstack_flights(flight_iata=clean_q, limit=3)
    if res.get("flights"):
        return res

    # 2. Try flight_icao directly
    res = query_aviationstack_flights(flight_icao=clean_q, limit=3)
    if res.get("flights"):
        return res

    # 3. Check local verified cache
    cache = load_cached_flights()
    # Check by key, flight_iata, registration, or icao24 in cache
    for k, f in cache.items():
        ac = f.get("aircraft") or {}
        reg = (ac.get("registration") or "").upper()
        hex_code = (ac.get("icao24") or "").upper()
        fn_iata = (f.get("flight", {}).get("iata") or "").upper()
        fn_icao = (f.get("flight", {}).get("icao") or "").upper()
        if clean_q in [k, reg, hex_code, fn_iata, fn_icao]:
            return {
                "status": "SUCCESS",
                "source": "aviationstack.com (cached data)",
                "total_results": 1,
                "flights": [f],
            }

    # 4. Check if clean_q is an aircraft registration or Mode S hex via hexdb
    icao24_target = None
    if len(clean_q) == 6 and all(c in "0123456789ABCDEF" for c in clean_q):
        icao24_target = clean_q.lower()
    else:
        meta = lookup_aircraft_metadata(clean_q)
        if meta and meta.get("ModeS"):
            icao24_target = meta["ModeS"].lower()

    # 5. Check worldwide OpenSky states to find active callsign for this aircraft
    if icao24_target:
        try:
            r_os = requests.get(f"https://opensky-network.org/api/states/all?icao24={icao24_target}", timeout=5)
            states = r_os.json().get("states", [])
            if states:
                active_callsign = states[0][1].strip()
                if active_callsign:
                    sub_res = query_aviationstack_flights(flight_iata=active_callsign, limit=1)
                    if not sub_res.get("flights"):
                        sub_res = query_aviationstack_flights(flight_icao=active_callsign, limit=1)
                    if sub_res.get("flights"):
                        return sub_res
        except Exception:
            pass

    return res


def get_aviationstack_flight_details(query: str) -> str:
    """Tool function to query AviationStack.com for real-time flight data by flight number (e.g. 'UA240', 'DL693', 'CX872', 'AA3101')
    OR by aircraft registration / Mode S ICAO hex (e.g. 'N552DT', 'A70736', 'N77576', 'AB6FDD').

    Returns comprehensive real-time flight information: airline, flight number, departure and arrival airports,
    terminal, gate, baggage claim, delay minutes, flight status, and aircraft details (registration and model).
    """
    res = search_flight_or_aircraft(query)
    if not res.get("flights"):
        return json.dumps({
            "status": "NOT_FOUND",
            "query": query,
            "message": f"No active flight record found in AviationStack for '{query}'. Please check the flight code or aircraft registration."
        }, indent=2)

    flight = res["flights"][0]
    dep = flight["departure"]
    arr = flight["arrival"]
    ac = flight["aircraft"]

    dep_delay_str = f"{dep['delay_minutes']} min delay" if dep.get('delay_minutes') else "On time"
    arr_delay_str = f"{arr['delay_minutes']} min delay" if arr.get('delay_minutes') else "On time"

    formatted_text = (
        f"FLIGHT INFORMATION FOR {flight['flight']['iata'] or flight['flight']['icao']} ({flight['airline']['name']}):\n"
        f"• Flight Status: {flight['flight_status'].upper()}\n"
        f"• Departure Airport: {dep['iata']} - {dep['airport']}\n"
        f"  - Terminal: {dep.get('terminal') or 'Main'}, Gate: {dep.get('gate') or 'TBD'}\n"
        f"  - Scheduled: {dep.get('scheduled') or 'N/A'}, Actual: {dep.get('actual') or dep.get('estimated') or 'N/A'}\n"
        f"  - Delay: {dep_delay_str}\n"
        f"• Arrival Airport: {arr['iata']} - {arr['airport']}\n"
        f"  - Terminal: {arr.get('terminal') or 'Main'}, Gate: {arr.get('gate') or 'TBD'}, Baggage Claim: {arr.get('baggage_claim') or 'TBD'}\n"
        f"  - Scheduled: {arr.get('scheduled') or 'N/A'}, Estimated: {arr.get('estimated') or 'N/A'}\n"
        f"  - Delay: {arr_delay_str}\n"
        f"• Aircraft Details:\n"
        f"  - Registration / Tail Number: {ac.get('registration') or 'N/A'}\n"
        f"  - Aircraft Model: {ac.get('model') or 'Commercial Jet'}\n"
        f"  - Mode S Transponder Hex: {ac.get('icao24') or 'N/A'}"
    )

    return json.dumps({
        "status": "SUCCESS",
        "source": res.get("source", "aviationstack.com"),
        "flight_summary_text": formatted_text,
        "flight_raw_data": flight,
    }, indent=2)


def list_aviationstack_airport_flights(airport_iata: str = "SFO", flight_type: str = "arrivals", limit: int = 5) -> str:
    """Tool function to list active or scheduled flights at an airport using AviationStack.com.

    Args:
        airport_iata: 3-letter IATA airport code (default 'SFO').
        flight_type: 'arrivals' or 'departures'.
        limit: Maximum number of flights to return (default 5).

    Returns:
        JSON string with real-time airport flight schedules, gates, terminals, delays, and aircraft info from AviationStack.com.
    """
    clean_airport = airport_iata.strip().upper()
    if flight_type.lower().startswith("dep"):
        result = query_aviationstack_flights(dep_iata=clean_airport, limit=limit)
    else:
        result = query_aviationstack_flights(arr_iata=clean_airport, limit=limit)
    return json.dumps(result, indent=2)
