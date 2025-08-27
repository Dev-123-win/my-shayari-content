mport json, os, sys, time, random
from datetime import datetime
from pathlib import Path

# pip install google-generativeai==0.8.3
import google.generativeai as genai

REPO_ROOT = Path(__file__).resolve().parents[1]
ONLINE_JSON = REPO_ROOT / "online_shayari.json"
PROMPT_FILE = REPO_ROOT / "content_automation" / "prompts" / "shayari_prompt.txt"

# Rotate through multiple API keys
API_KEYS = os.getenv("GEMINI_API_KEYS", "").split(",")  # set in GitHub Secrets
MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

def configure_gemini(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL)

def ask_model(model, prompt):
    resp = model.generate_content(prompt)
    return resp.text

def parse_or_fallback(text):
    # Try to parse JSON from model text; fallback to empty structure
    try:
        # Some models wrap JSON in code fences; strip them
        cleaned = text.strip().strip("`").replace("json", "")
        data = json.loads(cleaned)
        # Validate structure
        for k in ["love","sad","friendship","attitude","festival"]:
            data.setdefault(k, [])
        return data
    except Exception:
        return {k: [] for k in ["love","sad","friendship","attitude","festival"]}

def load_existing():
    if ONLINE_JSON.exists():
        with open(ONLINE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {k: [] for k in ["love","sad","friendship","attitude","festival"]}

def dedupe_keep_recent(arr):
    seen, out = set(), []
    for s in arr:
        key = s.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    # keep last 2,000 per category to limit size
    return out[-2000:]

def main():
    if not API_KEYS or not API_KEYS[0]:
        print("No GEMINI_API_KEYS provided.")
        sys.exit(1)

    prompt = open(PROMPT_FILE, "r", encoding="utf-8").read()
    existing = load_existing()

    # Try keys until success
    raw = None
    for key in API_KEYS:
        try:
            model = configure_gemini(key.strip())
            txt = ask_model(model, prompt)
            raw = parse_or_fallback(txt)
            # Ensure we got something non-empty
            if any(raw[k] for k in raw):
                break
        except Exception as e:
            print(f"Key failed, switching... {e}")
            time.sleep(2)
            continue

    if raw is None:
        print("All keys failed.")
        sys.exit(2)

    # Merge & dedupe
    for cat in ["love","sad","friendship","attitude","festival"]:
        merged = existing.get(cat, []) + raw.get(cat, [])
        existing[cat] = dedupe_keep_recent(merged)

    # Stamp update time
    existing["_meta"] = {"updated_at": datetime.utcnow().isoformat() + "Z"}

    with open(ONLINE_JSON, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print("online_shayari.json updated.")

if __name__ == "__main__":
    main()
