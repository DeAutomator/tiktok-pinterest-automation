import os
import json
import yt_dlp
import gspread
from google.oauth2.service_account import Credentials


# -----------------------------
# GOOGLE SHEETS CONNECTION
# -----------------------------

SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
SPREADSHEET_ID = os.environ["GOOGLE_SHEET_ID"]

credentials_info = json.loads(SERVICE_ACCOUNT_JSON)

scopes = [
    "https://www.googleapis.com/auth/spreadsheets"
]

credentials = Credentials.from_service_account_info(
    credentials_info,
    scopes=scopes
)

client = gspread.authorize(credentials)

spreadsheet = client.open_by_key(SPREADSHEET_ID)
sheet = spreadsheet.worksheet("Videos")


# -----------------------------
# READ SHEET DATA
# -----------------------------

all_rows = sheet.get_all_values()

if not all_rows:
    raise ValueError("The Google Sheet is empty.")

headers = [header.strip() for header in all_rows[0]]

required_headers = [
    "TikTok URL",
    "Creator",
    "Caption",
    "Video ID",
    "Thumbnail",
    "Video URL",
    "Status"
]

for header in required_headers:
    if header not in headers:
        raise ValueError(f"Missing column: {header}")

column = {
    name: headers.index(name) + 1
    for name in headers
}

# Collect video IDs already present in the sheet.
existing_ids = {
    row[column["Video ID"] - 1]
    for row in all_rows[1:]
    if len(row) >= column["Video ID"]
    and row[column["Video ID"] - 1].strip()
}


# -----------------------------
# TIKTOK SCRAPER
# -----------------------------

ydl_options = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True
}

with yt_dlp.YoutubeDL(ydl_options) as ydl:

    for row_number, row in enumerate(all_rows[1:], start=2):

        tiktok_url = (
            row[column["TikTok URL"] - 1].strip()
            if len(row) >= column["TikTok URL"]
            else ""
        )

        status = (
            row[column["Status"] - 1].strip()
            if len(row) >= column["Status"]
            else ""
        )

        if not tiktok_url or status.lower() != "new":
            continue

        print(f"Processing row {row_number}: {tiktok_url}")

        sheet.update_cell(
            row_number,
            column["Status"],
            "Processing"
        )

        try:
            info = ydl.extract_info(
                tiktok_url,
                download=False
            )

            video_id = str(info.get("id") or "")

            if not video_id:
                raise ValueError("Could not extract a video ID.")

            if video_id in existing_ids:
                sheet.update_cell(
                    row_number,
                    column["Status"],
                    "Duplicate"
                )
                print(f"Duplicate video skipped: {video_id}")
                continue

            creator = (
                info.get("uploader")
                or info.get("channel")
                or info.get("uploader_id")
                or ""
            )

            caption = (
                info.get("description")
                or info.get("title")
                or ""
            )

            thumbnail = info.get("thumbnail") or ""

            # Update the metadata columns.
            # Video URL is left blank for now because
            # temporary TikTok stream URLs can expire.
            values = [
                creator,
                caption,
                video_id,
                thumbnail,
                ""
            ]

            for offset, value in enumerate(values):
                sheet.update_cell(
                    row_number,
                    column["Creator"] + offset,
                    value
                )

            sheet.update_cell(
                row_number,
                column["Status"],
                "Ready"
            )

            existing_ids.add(video_id)

            print(f"Successfully processed: {video_id}")

        except Exception as error:
            print(f"Error processing row {row_number}: {error}")

            sheet.update_cell(
                row_number,
                column["Status"],
                "Failed"
            )

print("Scraper finished.")
