
import os
import glob
import tempfile
import requests
import yt_dlp

TIKTOK_URL = os.environ["TIKTOK_URL"]
ROW_NUMBER = os.environ["ROW_NUMBER"]
MAKE_WEBHOOK_URL = os.environ["MAKE_WEBHOOK_URL"]


def scrape_video():

    print(f"Downloading TikTok video: {TIKTOK_URL}")

    with tempfile.TemporaryDirectory() as temp_dir:

        ydl_options = {
            "outtmpl": os.path.join(temp_dir, "video.%(ext)s"),
            "format": "best",
            "merge_output_format": "mp4",
            "quiet": False,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(
                TIKTOK_URL,
                download=True
            )

        files = glob.glob(os.path.join(temp_dir, "video.*"))

        files = [
            f for f in files
            if not f.endswith((".part", ".ytdl"))
        ]

        if not files:
            raise Exception("Downloaded video file not found.")

        video_path = files[0]

        creator = (
            info.get("uploader")
            or info.get("channel")
            or "Unknown"
        )

        caption = (
            info.get("description")
            or info.get("title")
            or ""
        )

        video_id = str(info.get("id", ""))
        thumbnail = info.get("thumbnail", "")

        print("Download completed.")
        print("Sending video and metadata to Make...")

        data = {
            "tiktok_url": TIKTOK_URL,
            "row_number": ROW_NUMBER,
            "video_id": video_id,
            "creator": creator,
            "caption": caption,
            "thumbnail": thumbnail,
        }

        with open(video_path, "rb") as video_file:

            files = {
                "video": (
                    "video.mp4",
                    video_file,
                    "video/mp4"
                )
            }

            response = requests.post(
                MAKE_WEBHOOK_URL,
                data=data,
                files=files,
                timeout=300
            )

        response.raise_for_status()

        print("Successfully sent video to Make!")
        print(response.text)


if __name__ == "__main__":
    scrape_video()
