import os
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

def capture_snapshot(youtube_url, output_path):
    """Captures a snapshot frame via streamlink (bypasses YouTube datacenter IP blocks)."""
    temp_ts = output_path + ".ts"
    try:
        if os.path.exists(temp_ts):
            os.remove(temp_ts)
        if os.path.exists(output_path):
            os.remove(output_path)

        # 1. Grab 3 seconds of stream via streamlink
        cmd_streamlink = [
            "streamlink",
            "--output", temp_ts,
            "--force",
            "--max-stream-duration", "3",
            youtube_url,
            "worst"
        ]
        res_sl = subprocess.run(cmd_streamlink, capture_output=True, text=True, timeout=30)
        
        if not os.path.exists(temp_ts) or os.path.getsize(temp_ts) == 0:
            print(f"  ❌ streamlink error: {res_sl.stderr.strip()}")
            return False

        # 2. Extract 1 snapshot frame via ffmpeg
        cmd_ffmpeg = [
            "ffmpeg", "-y",
            "-i", temp_ts,
            "-vframes", "1",
            "-q:v", "2",
            output_path
        ]
        res_ff = subprocess.run(cmd_ffmpeg, capture_output=True, text=True, timeout=20)
        
        if os.path.exists(temp_ts):
            os.remove(temp_ts)

        success = os.path.exists(output_path) and os.path.getsize(output_path) > 0
        if not success:
            print(f"  ❌ ffmpeg extraction error: {res_ff.stderr.strip()}")
        return success

    except Exception as e:
        print(f"  ❌ Exception during snapshot capture: {e}")
        if os.path.exists(temp_ts):
            os.remove(temp_ts)
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
        snap_path = f"snap_cam_{cam['id']}.jpg"

        if capture_snapshot(cam['url'], snap_path):
            is_raining = check_rain_with_ai(snap_path, cam['name'])
            status_report[str(cam['id'])] = {
                "is_raining": is_raining,
                "status": "online",
                "last_updated": timestamp
            }
            print(f"  Result: {'RAINING 🌧️' if is_raining else 'DRY ☁️'}")
            
            if os.path.exists(snap_path):
                os.remove(snap_path)
        else:
            status_report[str(cam['id'])] = {
                "is_raining": False,
                "status": "offline",
                "last_updated": timestamp
            }

    # Mirror Cam 2's result over to Cam 1 (Genmiskih Fannu ~147m away)
    if "2" in status_report:
        status_report["1"] = {
            "is_raining": status_report["2"]["is_raining"],
            "status": status_report["2"]["status"],
            "last_updated": timestamp
        }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(status_report, f, indent=2)
    print(f"Successfully updated {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
