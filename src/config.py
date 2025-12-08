import os
from dotenv import load_dotenv

load_dotenv()

def get_env(name: str, default=None, required: bool = False):
    value = os.environ.get(name, default)
    if required and value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

CALENDAR_URL     = get_env("CALENDAR_URL", required=True)
WIKI_API_URL     = get_env("WIKI_API_URL", required=True)
WIKI_PAGE_TITLE  = get_env("WIKI_PAGE_TITLE", required=True)
EDIT_SUMMARY     = get_env("EDIT_SUMMARY", "refreshed via script")

WIKI_USERNAME    = get_env("WIKI_USERNAME", required=True)
WIKI_PASSWORD    = get_env("WIKI_PASSWORD", required=True)

INFO_TEXT        = get_env("INFO_TEXT", "")

LINK_KEYWORDS    = get_env("LINK_KEYWORDS", "")