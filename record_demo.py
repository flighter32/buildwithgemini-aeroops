import os
import time
import glob
import subprocess
from playwright.sync_api import sync_playwright

VIDEO_DIR = "/config/Desktop/BuildWithGemini/video_raw"
FINAL_VIDEO = "/config/Desktop/BuildWithGemini/aeroops_demo.mp4"
ARTIFACT_VIDEO = "/config/.gemini/antigravity/brain/42f27460-1951-4808-8476-2e6e0b0a8297/aeroops_demo.mp4"

os.makedirs(VIDEO_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--enable-blink-features=AnimationWorklet"]
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1280, "height": 800}
    )
    page = context.new_page()
    
    print("[1/5] Navigating to AeroOps ADK Playground...")
    page.goto("http://localhost:8080", wait_until="networkidle")
    time.sleep(3) # Let UI settle and show prompts bar

    # Turn 1: Click the tailored prompt chip: "📍 Where is flight UA240? Show flight map"
    print("[2/5] Selecting prompt chip: Where is flight UA240? Show flight map...")
    chip = page.query_selector('.aeroops-chip[data-prompt*="UA240"]')
    if not chip:
        chip = page.query_selector('.aeroops-chip')
    
    chip.hover()
    time.sleep(1)
    chip.click()
    
    print("[3/5] Waiting for AviationStack + Maps + Nano Banana visual card response...")
    # Wait until card appears or up to 20 seconds
    for _ in range(25):
        time.sleep(1)
        # Check if card image or event 3 has loaded
        card_img = page.query_selector('img')
        if card_img:
            print("Visual card image rendered!")
            break

    # Pause on the generated visual card to admire the Banana mascot & Google Maps overlay
    time.sleep(6)

    # Turn 2: Ask a richer, domain-specific operational turnaround query
    print("[4/5] Typing Turn 2 prompt: Turnaround Delay Estimation & Gate Analysis...")
    textarea = page.query_selector("textarea")
    textarea.click()
    prompt2_text = "Estimate turnaround delay for flight UA240 at Gate B4"
    for char in prompt2_text:
        page.keyboard.type(char, delay=25)
    time.sleep(1)
    page.keyboard.press("Enter")

    print("[5/5] Waiting for Turn 2 tool calls and operational breakdown...")
    for _ in range(25):
        time.sleep(1)
        # Check if turn 2 response arrived
        txt = page.evaluate("() => document.body.innerText")
        if "Turnaround Operational Breakdown" in txt or "Projected Outbound Departure Delay" in txt:
            print("Turnaround analysis rendered!")
            break

    # Let the final screen display clearly
    time.sleep(6)

    context.close()
    browser.close()

# Find the recorded webm file
webm_files = glob.glob(f"{VIDEO_DIR}/*.webm")
if webm_files:
    latest_webm = max(webm_files, key=os.path.getctime)
    print(f"Recorded raw video: {latest_webm}")
    
    # Convert to MP4 with H.264 for universal compatibility
    cmd = [
        "ffmpeg", "-y",
        "-i", latest_webm,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "22",
        FINAL_VIDEO
    ]
    subprocess.run(cmd, check=True)
    print(f"Successfully exported MP4: {FINAL_VIDEO}")

    # Copy to artifacts directory
    subprocess.run(["cp", FINAL_VIDEO, ARTIFACT_VIDEO], check=True)
    print(f"Copied to artifact dir: {ARTIFACT_VIDEO}")
else:
    print("Error: No webm file found!")
