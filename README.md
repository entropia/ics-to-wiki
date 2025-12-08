# ics-to-wiki

A simple Python script to convert iCalendar (.ics) files into a wiki-friendly table.

## Installation

### Requirements

- Python 3.9+
- A MediaWiki installation with API access enabled
- Packages:
    - requests
    - python-dotenv
    - icalendar
    - python-dateutil

### Environment

Copy the `.env.example` file to `.env` and fill in your data.

- `CALENDAR_URL` - URL to the .ics calendar file.
- `WIKI_API_URL` - URL to the MediaWiki API endpoint (usually ends with `/api.php`).
- `WIKI_PAGE_TITLE` - Title of the wiki page to update.
- `EDIT_SUMMARY` - Edit summary for the wiki page update.
- `WIKI_USERNAME` - Your MediaWiki username.
- `WIKI_PASSWORD` - Your MediaWiki password.
- `INFO_TEXT` - (Optional) Additional information text to include above the table.
- `LINK_KEYWORDS` - (Optional) Comma-separated keywords to convert matching event titles into wiki links.
    - Example: `Entropia=[[Entropia]]엔트로피Hackerfrystyck=[[Hackerfrystyck]]`
    - This will convert any event title containing "Entropia" into a link to the "Entropia" wiki page.
    - Split multiple replacements with `엔트로피`.

### Usage

Just run the script with valid environment variables.
The script will replace the whole content of the specified wiki
page with a table generated from the .ics file.
