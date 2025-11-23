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

### Usage

Just run the script with valid environment variables.
The script will replace the whole content of the specified wiki
page with a table generated from the .ics file.
