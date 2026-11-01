import os
import cv2
import json
import subprocess
from datetime import datetime
from google import genai
from google.genai import types

# Initialize Gemini Client using API key stored in GitHub Actions Secrets
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

CAMERAS_TO_ANALYZE = [
    {"id": 2, "name": "Genmiskih Area", "url": "https://www.youtube.com/watch?v=dJ3lcom_xk8"},
    {"id": 3, "name": "Fish Market", "url": "https://www.youtube.com/watch?v=GW5qgbT80oA"}
]

OUTPUT_FILE = "rain_status.json"

def get_stream_url(youtube_url):
    try:
        cmd = ["yt-dlp", "-g", youtube_url]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8').strip()
        return output.splitlines()[0] if output else None
    except Exception as e:
        print(f"Error fetching stream URL: {e}")
        return None

def capture_snapshot(stream_url, output_path):
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        return False
    
    ret, frame = cap.read()
    cap.release()
    
    if ret and frame is not None:
        cv2.imwrite(output_path, frame)
        return True
    return False

def check_rain_with_ai(image_path, camera_name):
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        prompt = (
            f"This is a security camera snapshot from '{camera_name}' in Fuvahmulah, Maldives.\n"
            "Task: Determine if active natural rain is falling in this scene.\n"
            "- Look for falling raindrops, vertical rain streaks in the air, atmospheric haze, or rain splatters.\n"
            "- CRITICAL RULE: Ignore workers hosing down the ground, hose water streams, floor cleaning shifts, and passing people/vehicles.\n"
            "Respond ONLY with a JSON object in this exact format: {\"is_raining\": true} or {\"is_raining\": false}"
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            ]
        )

        text_response = response.text.lower()
        return '"is_raining": true' in text_response or '"is_raining":true' in text_response
    except Exception as e:
        print(f"AI Vision API error on {camera_name}: {e}")
        return False

def main():
    status_report = {}
    timestamp = datetime.now().strftime("%I:%M %p")

    for cam in CAMERAS_TO_ANALYZE:
        print(f"Analyzing Camera {cam['id']}: {cam['name']} using Vision AI...")
        stream_url = get_stream_url(cam['url'])
        snap_path = f"snap_cam_{cam['id']}.jpg"

        if stream_url and capture_snapshot(stream_url, snap_path):
            is_raining = check_rain_with_ai(snap_path, cam['name'])
            status_report[cam['id']] = {
                "is_raining": is_raining,
                "status": "online",
                "last_updated": timestamp
            }
            print(f"  Result: {'RAINING 🌧️' if is_raining else 'DRY ☁️'}")
            
            if os.path.exists(snap_path):
                os.remove(snap_path)
        else:
            status_report[cam['id']] = {
                "is_raining": False,
                "status": "offline",
                "last_updated": timestamp
            }

    # Mirror Cam 2's result over to Cam 1 (Genmiskih Fannu ~147m away)
    if 2 in status_report:
        status_report[1] = {
            "is_raining": status_report[2]["is_raining"],
            "status": status_report[2]["status"],
            "last_updated": timestamp
        }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(status_report, f, indent=2)
    print(f"Successfully updated {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
