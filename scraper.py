
import os
import json
import tempfile
import mimetypes
from pathlib import Path

import gspread
import requests
import yt_dlp


def main():
    # Read information sent by Make through GitHub Actions
    tiktok_url = os.environ["TIKTOK_URL"]
    row_number = int(os.environ["ROW_NUMBER"])
    webhook_url = os.environ["MAKE_WEBHOOK_URL"]

    # Connect to Google Sheets
    credentials = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    client = gspread.service_account_from_dict(credentials)

    spreadsheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
    sheet = spreadsheet.worksheet("Videos")

    # Make sure this is the correct row
    row = sheet.row_values(row_number)

    if not row or row[0].strip() != tiktok_url.strip():
        raise ValueError("The TikTok URL does not match the selected sheet row.")

    status = row[8].strip() if len(row) >= 9 else ""

    if status not in ("New", "Processing"):
        raise ValueError(f"Row {row_number} has an unexpected status: {status}")

    try:
        sheet.update_acell(f"I{row_number}", "Processing")

        # Download only this TikTok video
        with tempfile.TemporaryDirectory() as temp_dir:
            output_template = str(Path(temp_dir) / "video.%(ext)s")

            options = {
                "outtmpl": output_template,
                "format": "best",
                "noplaylist": True,
                "quiet": False,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(tiktok_url, download=True)

            # Find the downloaded video file
            video_files = [
                file for file in Path(temp_dir).iterdir()
                if file.is_file() and not file.name.endswith(".part")
            ]

            if not video_files:
                raise RuntimeError("The video download completed, but no video file was found.")

            video_path = max(video_files, key=lambda file: file.stat().st_size)

            # Extract video details
            creator = info.get("uploader") or info.get("channel") or ""
            caption = info.get("description") or info.get("title") or ""
            video_id = info.get("id") or ""
            thumbnail = info.get("thumbnail") or ""

            # Update metadata in Google Sheets
            sheet.update(
                f"B{row_number}:F{row_number}",
                [[creator, caption, video_id, thumbnail, ""]],
                value_input_option="RAW",
            )

            # Send the video and its details to Make
            mime_type = mimetypes.guess_type(video_path.name)[0] or "application/octet-stream"

            form_data = {
                "video_id": video_id,
                "tiktok_url": tiktok_url,
                "creator": creator,
                "caption": caption,
                "thumbnail": thumbnail,
                "row_number": str(row_number),
            }

            with open(video_path, "rb") as video_file:
                response = requests.post(
                    webhook_url,
                    data=form_data,
                    files={
                        "video": (video_path.name, video_file, mime_type)
                    },
                    timeout=300,
                )

            response.raise_for_status()

            print(f"Successfully sent row {row_number} to Make.")

            # Leave the row as Processing.
            # Make will change it to Published after Pinterest publishing succeeds.


    except Exception as error:
        sheet.update_acell(f"I{row_number}", "Failed")
        print(f"Failed to process row {row_number}: {error}")
        raise


if __name__ == "__main__":
    main()
