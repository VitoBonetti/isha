import os
import base64
import json
import re
import uuid
import requests
from fastapi import FastAPI, Request, HTTPException
from google.cloud import secretmanager, storage
import google.generativeai as genai
import google.auth.transport.requests
import google.oauth2.id_token

app = FastAPI()

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
GEMINI_KEY_NAME = os.environ.get("GEMINI_KEY_NAME")
MAIN_BACKEND_URL = os.environ.get("MAIN_BACKEND_URL")
IAP_CLIENT_ID = os.environ.get("IAP_CLIENT_ID")
LUIGI_SKILLS_BUCKET_NAME = os.environ.get("LUIGI_SKILLS_BUCKET_NAME")

# --- Security: Fetch API Key ---
def get_gemini_key():
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{GEMINI_KEY_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


# --- Security: Dynamic IAM Token for Backend ---
def get_iam_token():
    """Fetches a dynamic OIDC token to authenticate with the main backend."""
    req = google.auth.transport.requests.Request()
    return google.oauth2.id_token.fetch_id_token(req, IAP_CLIENT_ID)


# --- Fetch Skill from GCS Bucket ---
def get_skill_prompt(skill_name: str) -> str:
    """Downloads the specific markdown skill file from the GCS bucket."""
    try:
        client = storage.Client()
        bucket = client.bucket(LUIGI_SKILLS_BUCKET_NAME)
        blob = bucket.blob(f"{skill_name}/{skill_name}.md")

        if not blob.exists():
            raise Exception(f"Skill file '{skill_name}.md' not found in bucket '{LUIGI_SKILLS_BUCKET_NAME}'.")

        return blob.download_as_text()
    except Exception as e:
        raise Exception(f"Failed to load skill from bucket: {str(e)}")


# --- Subagent: Vision Summarizer ---
def sub_luigi_vision(gcs_uri: str, specific_question: str) -> str:
    """
    Analyzes an evidence image from Google Cloud Storage to verify specific technical claims.

    Args:
        gcs_uri: The Google Cloud Storage URI of the image (e.g., gs://bucket/path/to/image.png).
        specific_question: A highly specific question about what to look for in the image to verify the fix.
    """
    print(f"👀 Tool Called: Inspecting {gcs_uri} for '{specific_question}'")
    try:
        storage_client = storage.Client()
        parts = gcs_uri.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(parts[0])
        blob = bucket.blob(parts[1])

        # Use a random UUID to prevent collisions if multiple tools run concurrently
        temp_file_path = f"/tmp/{uuid.uuid4().hex}_{parts[1].split('/')[-1]}"
        blob.download_to_filename(temp_file_path)

        g_file = genai.upload_file(temp_file_path)

        vision_model = genai.GenerativeModel('gemini-2.5-pro')
        response = vision_model.generate_content([specific_question, g_file])
        analysis = response.text.strip()

        genai.delete_file(g_file.name)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        return analysis
    except Exception as e:
        return f"Failed to analyze image: {str(e)}"


# --- Main Logic Trigger ---
@app.post("/")
async def pubsub_trigger(request: Request):
    envelope = await request.json()
    if not envelope or "message" not in envelope:
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub format")

    data = json.loads(base64.b64decode(envelope["message"]["data"]).decode("utf-8"))
    task_type = data.get("task")

    # We only care about scheduling meetings now
    if task_type == "SCHEDULE_MEETING":
        print(f"🗓️ Luigi analyzing calendars for test: {data.get('test_name')}")

        try:
            genai.configure(api_key=get_gemini_key())
            model = genai.GenerativeModel('gemini-2.5-pro')

            sys_prompt = f"""
            You are a highly intelligent scheduling assistant. 
            Your task is to find the best times for a 45-minute '{data.get('meeting_type')}' meeting for the pentest '{data.get('test_name')}'.

            Here is the Free/Busy JSON data from Google Calendar for all participants:
            {json.dumps(data.get('free_busy'))}

            RULES:
            1. Find 3 to 4 mutually available 45-minute slots. 
            2. STRICT TIMEZONE RULE: You must prioritize overlapping business hours (09:00 - 17:00) between Amsterdam (CET/CEST) AND the local time in {data.get('country_name', 'the target country')}. NEVER schedule a meeting that falls before 08:00 AM or after 18:00 PM in either of those local timezones.
            3. If a perfect match for everyone is impossible, propose a slot that works for the majority, but flag who has a conflict. Alternatively, propose a 30-minute slot.
            4. Format the start and end times in strict ISO 8601 format in UTC (e.g., 2026-08-25T10:00:00Z).

            Return ONLY a raw JSON array of objects with exactly this structure:
            [
              {{
                 "start_time": "ISO format",
                 "end_time": "ISO format",
                 "description": "Perfect match for everyone.",
                 "duration_mins": 45
              }}
            ]
            """

            response = model.generate_content(sys_prompt)
            raw_text = response.text.strip()

            # Clean markdown formatting if Gemini wrapped it in ```json ... ```
            start_idx = raw_text.find('[')
            end_idx = raw_text.rfind(']')
            clean_json = raw_text[start_idx:end_idx + 1] if start_idx != -1 else raw_text

            proposals = json.loads(clean_json)

            # Send back to main backend
            url = f"{MAIN_BACKEND_URL}/api/luigi/save-meeting-proposals"
            headers = {"Authorization": f"Bearer {get_iam_token()}"}

            payload = {
                "test_id": data.get("test_id"),
                "test_name": data.get("test_name"),
                "user_email": data.get("user_email"),
                "meeting_type": data.get("meeting_type"),
                "proposals": proposals,
                "emails": data.get("emails")  # Passing this back so the UI knows who to invite!
            }

            save_res = requests.post(url, json=payload, headers=headers)
            save_res.raise_for_status()

            print(f"✅ Luigi successfully returned proposals for: {data.get('test_name')}")
            return {"status": "success"}

        except Exception as e:
            print(f"🚨 Luigi error: {e}")
            return {"status": "error", "detail": str(e)}


    elif task_type == "DRAFT_VULNERABILITY":
        print(f"📝 Luigi dynamically drafting vulnerability for: {data.get('user_email')}")
        try:
            # For now, we hardcode the skill name, but later you can pass it in the payload!
            base_skill_markdown = get_skill_prompt(str(task_type))

            # 2. Append the specific task data and strict formatting rules
            sys_prompt = f"""
                {base_skill_markdown}
                =========================================
                CURRENT TASK DATA:
                Severity: {data.get('severity')}
                Pentester Notes: {data.get('note')}
                =========================================

                STRICT SYSTEM ENFORCEMENT FOR OUTPUT:
                You MUST return your response using EXACTLY these custom delimiters so the backend parser can read it. Do NOT output standard JSON. Do NOT wrap the output in markdown ticks.

                [SUGGESTED_TYPE]
                Write the CWE Name here (e.g., CWE-79: Improper Neutralization...)
                [/SUGGESTED_TYPE]

                [HTML_BODY]
                Write the complete raw HTML code here, following the examples provided in the persona above.
                [/HTML_BODY]
                """

            # 3. Configure AI & Generate
            genai.configure(api_key=get_gemini_key())
            model = genai.GenerativeModel('gemini-2.5-pro')
            response = model.generate_content(sys_prompt)
            raw_text = response.text.strip()

            # 4. Extract Custom Tags Safely
            type_match = re.search(r'\[SUGGESTED_TYPE\](.*?)\[/SUGGESTED_TYPE\]', raw_text, re.DOTALL | re.IGNORECASE)
            html_match = re.search(r'\[HTML_BODY\](.*?)\[/HTML_BODY\]', raw_text, re.DOTALL | re.IGNORECASE)
            suggested_type = type_match.group(1).strip() if type_match else "CWE-Unknown"
            html_content = html_match.group(1).strip() if html_match else raw_text
            html_content = re.sub(r'^```[a-zA-Z]*\s*', '', html_content, flags=re.IGNORECASE)
            html_content = re.sub(r'\s*```$', '', html_content)
            html_content = html_content.strip()
            html_content = re.sub(r"(?i)<h1>\s*<span\s+style=['\"]color:\s*#[0-9a-fA-F]+['\"]\s*>",
                                  "<h1><span style='color:#2175d9'>", html_content)

            # 5. Webhook Callback
            url = f"{MAIN_BACKEND_URL}/api/luigi/vuln-draft-callback"
            headers = {"Authorization": f"Bearer {get_iam_token()}"}
            payload = {
                "user_email": data.get("user_email"),
                "html": html_content,
                "suggested_type": suggested_type
            }

            save_res = requests.post(url, json=payload, headers=headers)
            save_res.raise_for_status()
            print(f"✅ Luigi successfully drafted vulnerability for {data.get('user_email')}")
            return {"status": "success"}

        except Exception as e:
            print(f"🚨 Luigi error drafting vuln: {e}")
            return {"status": "error", "detail": str(e)}


    elif task_type == "VERIFY_VULN":
        print(f"🤖 Luigi starting agentic verification for: {data.get('vuln_uuid')}")

        try:
            genai.configure(api_key=get_gemini_key())
            vuln_data = data.get("vuln_data")
            skill_instructions = get_skill_prompt("VERIFY_VULN")

            # 1. Initialize Main Luigi with the Vision Tool!
            main_model = genai.GenerativeModel(
                model_name='gemini-2.5-pro',
                tools=[sub_luigi_vision]
            )

            # 2. Start an automated chat loop
            chat = main_model.start_chat(enable_automatic_function_calling=True)

            sys_prompt = f"""
                {skill_instructions}
                JSON TIMELINE:
                {json.dumps(vuln_data, indent=2)}
                """

            # 3. Send the prompt. Luigi will pause, call the tool if needed, read the result, and finish!
            response = chat.send_message(sys_prompt)
            final_verdict = response.text.strip()

            # 4. Callback to Mario
            url = f"{MAIN_BACKEND_URL}/api/luigi/validation-callback"
            headers = {"Authorization": f"Bearer {get_iam_token()}"}
            payload = {
                "vuln_uuid": data.get("vuln_uuid"),
                "ai_suggestion": final_verdict,
                "gcs_uris": data.get("cleanup_uris", [])
            }

            requests.post(url, json=payload, headers=headers).raise_for_status()
            print(f"✅ Luigi verification complete for {data.get('vuln_uuid')}")
            return {"status": "success"}

        except Exception as e:
            print(f"🚨 Luigi error: {e}")
            return {"status": "error", "detail": str(e)}


    return {"status": "ignored", "detail": "Task type not supported"}