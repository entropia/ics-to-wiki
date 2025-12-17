import os
import tomli

config_path = os.path.join(os.path.dirname(__file__), "..", "config.toml")
with open(config_path, "rb") as f:
    config = tomli.load(f)

def get(key, default=None, required=False):
    if key in config:
        return config[key]
    if required:
        raise KeyError(f"Missing required configuration key: {key}")
    return default

CALENDAR_URL = get("calendar", {}).get("url", "")
REPLACE_LINKS = get("calendar", {}).get("replace_links", [])
WIKI_API_URL = get("wiki", {}).get("api_url", "")
WIKI_PAGE_TITLE = get("wiki", {}).get("page_title", "")
WIKI_USERNAME = get("wiki", {}).get("username", "")
WIKI_PASSWORD = get("wiki", {}).get("password", "")
EDIT_SUMMARY = get("wiki", {}).get("edit_summary", {})
INFO_TEXT = get("wiki", {}).get("info", {})
