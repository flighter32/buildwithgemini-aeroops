# My agent: Airport Operations & Flight Dispatch Assistant (AeroOps)
One-liner: A conversational agent that helps airport ground staff and dispatchers track live flights, inspect gate and aircraft states, visualize terminal maps, and estimate turnaround delays.

Tool coverage:
- Memory: Remembers assigned staff roles, shift preferences, airport hub context (e.g. SFO/JFK), watched priority flights, and past incident flags across sessions.
- Tools: Live flight schedule & status lookup (AviationStack / OpenSky / mock flight API), gate assignment lookup, and aircraft state telemetry tracking.
- Catalog/UI: Flight status board cards, gate details, and aircraft inspection checklists rendered as rich A2UI cards/tables.
- Image gen: Generates visual airport gate/terminal maps, apron layout overviews, or visual weather radar overlays.
- Sandbox: Delay calculation engine running Python in the code sandbox (computes turnaround time buffer, taxiway congestion delay, and weather impact estimates).

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits): Code execution sandbox for flight delay modeling, live external flight tracking API (e.g. OpenSky Network or FlightAware), interactive terminal layout rendering.
