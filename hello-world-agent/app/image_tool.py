"""Image generation tool for airport operations and flight dispatch.

Uses the gemini-3.1-flash-lite-image model in the global region.
Saves the generated image as an ADK artifact (tool_context.save_artifact)
and uploads the image bytes to the public Cloud Storage bucket:
gs://bwg3-qwiklabs-gcp-03-1e9929f2d46c
Returning its public https URL.
"""

import os
import uuid
import json
from typing import Optional
from google import genai
from google.genai import types
from google.cloud import storage
from google.adk.tools import ToolContext

from .aviationstack import search_flight_or_aircraft

PUBLIC_BUCKET_NAME = "bwg3-qwiklabs-gcp-03-1e9929f2d46c"
PROJECT_ID = "qwiklabs-gcp-03-1e9929f2d46c"
LOCATION = "global"
MODEL_NAME = "gemini-3.1-flash-lite-image"


async def generate_dispatch_visual_map(
    item_or_flight: str,
    tool_context: ToolContext,
    visual_type: str = "radar_flight_map",
) -> str:
    """Generates an airport operations or flight visual image using gemini-3.1-flash-lite-image
    based on REAL flight telemetry and schedule data fetched from AviationStack.

    The generated image is:
    1. Saved as an ADK artifact using `tool_context.save_artifact` so it appears in the Playground Artifacts panel.
    2. Uploaded directly to the public Cloud Storage bucket `bwg3-qwiklabs-gcp-03-1e9929f2d46c`.
    3. Returned with its directly accessible public HTTPS URL.

    Args:
        item_or_flight: The flight callsign, number, or aircraft registration (e.g. 'UA240', 'DL693', 'N552DT', 'AA3101').
        visual_type: Type of visualization ('flight_dispatch', 'radar_flight_map', 'gate_terminal_layout').
        tool_context: The ADK tool execution context for saving artifacts.

    Returns:
        JSON string containing the public image URL, artifact filename, and summary of the generated visualization.
    """
    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )

    # 1. Fetch real-time flight details from AviationStack to bind real data into the image prompt!
    av_res = search_flight_or_aircraft(item_or_flight)
    flight = av_res.get("flights", [{}])[0] if av_res.get("flights") else {}

    airline_name = flight.get("airline", {}).get("name") or "Commercial Airline"
    flight_iata = flight.get("flight", {}).get("iata") or item_or_flight
    flight_status = (flight.get("flight_status") or "ACTIVE").upper()

    dep = flight.get("departure") or {}
    arr = flight.get("arrival") or {}
    ac = flight.get("aircraft") or {}

    dep_iata = dep.get("iata") or "DEP"
    dep_gate = dep.get("gate") or "TBD"
    dep_delay = dep.get("delay_minutes") or 0

    arr_iata = arr.get("iata") or "SFO"
    arr_gate = arr.get("gate") or "TBD"
    arr_delay = arr.get("delay_minutes") or 0

    aircraft_reg = ac.get("registration") or "N/A"
    aircraft_model = ac.get("model") or "Commercial Jet"

    dep_status_str = f"DELAY {dep_delay}M" if dep_delay > 0 else "ON TIME"
    arr_status_str = f"DELAY {arr_delay}M" if arr_delay > 0 else "ON TIME"

    prompt = (
        f"Generate a cinematic, high-tech airline operations display for flight {flight_iata} ({airline_name}). "
        f"The display MUST prominently integrate the real-time flight data into glowing digital HUD graphics: "
        f"- Flight: '{flight_iata}' | Airline: '{airline_name}'\n"
        f"- Route: '{dep_iata}' (Gate {dep_gate}, {dep_status_str}) to '{arr_iata}' (Gate {arr_gate}, {arr_status_str})\n"
        f"- Aircraft: '{aircraft_model}' | Tail Number: '{aircraft_reg}'\n"
        f"- Flight Status: '{flight_status}'\n"
        "Features a cute 3D cartoon banana pilot mascot wearing pilot aviator sunglasses and captain uniform at the bottom corner, "
        "pointing to a glowing geospatial flight route map in the center. "
        "Futuristic air traffic control interface, dark navy blue and slate backdrop with glowing electric cyan, gold, and amber telemetry fonts."
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="16:9"),
            ),
        )

        img_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    img_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not img_bytes:
            return json.dumps({
                "status": "ERROR",
                "error": "The image generation model did not return image bytes.",
            })

        safe_slug = "".join(c if c.isalnum() else "_" for c in item_or_flight.lower()).strip("_")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"dispatch_{safe_slug}_{unique_id}.jpg"

        # 1. Save as ADK artifact so it appears in the Playground Artifacts panel
        artifact_part = types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload to public Cloud Storage bucket
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(PUBLIC_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(img_bytes, content_type=mime_type)

        public_https_url = f"https://storage.googleapis.com/{PUBLIC_BUCKET_NAME}/{filename}"

        return json.dumps({
            "status": "SUCCESS",
            "item": item_or_flight,
            "artifact_filename": filename,
            "public_image_url": public_https_url,
            "description": f"Generated high-definition dispatch image for {flight_iata} (Tail: {aircraft_reg}, {dep_iata} -> {arr_iata}) with integrated real-time AviationStack metrics and Banana mascot.",
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "ERROR",
            "error": f"Failed to generate and upload image: {str(e)}",
        })
