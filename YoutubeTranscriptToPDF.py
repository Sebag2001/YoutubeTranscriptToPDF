import json
import os
import re
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from urllib.request import Request, urlopen

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from youtube_transcript_api import YouTubeTranscriptApi


def parse_link(url):
    """Analyze the URL to determine if it is a playlist or a single video.

    Returns a dictionary containing the type ('playlist' or 'video') and its ID.
    """
    playlist_pattern = re.search(r"[?&]list=([^#\&\?]+)", url)
    if playlist_pattern:
        return {"type": "playlist", "id": playlist_pattern.group(1)}

    video_pattern = re.search(
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/)([^#\&\?]{11})", url
    )
    if video_pattern:
        return {"type": "video", "id": video_pattern.group(1)}

    return {"type": "video", "id": url}


def get_video_title(video_id):
    """Fetch the video title using YouTube's public oEmbed API."""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        response = urlopen(url)
        data = json.loads(response.read().decode())
        return data.get("title", f"Video_{video_id}")
    except Exception:
        return f"Video_{video_id}"


def get_playlist_title(playlist_id):
    """Fetch the playlist title using YouTube's public oEmbed API."""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/playlist?list={playlist_id}&format=json"
        response = urlopen(url)
        data = json.loads(response.read().decode())
        return data.get("title", f"Playlist_{playlist_id}")
    except Exception:
        return f"Playlist_{playlist_id}"


def sanitize_filename(title):
    """Remove OS-incompatible characters and limit the length of the filename."""
    clean_name = re.sub(r'[\\/*?:"<>|]', "_", title)
    clean_name = " ".join(clean_name.split())
    if len(clean_name) > 80:
        return clean_name[:77] + "..."
    return clean_name


def extract_playlist_video_ids(playlist_id):
    """Scrape the playlist page to extract all video IDs from the internal JSON."""
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urlopen(req).read().decode("utf-8")
        found_matches = re.findall(r'"videoId":"([^"]{11})"', html)

        unique_ids = []
        for vid in found_matches:
            if vid not in unique_ids:
                unique_ids.append(vid)
        return unique_ids
    except Exception:
        return []


def format_timestamp(seconds):
    """Convert float seconds into a readable [HH:MM:SS] or [MM:SS] format."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"
    return f"[{minutes:02d}:{secs:02d}]"


def get_native_transcript(video_id, include_time):
    """Download the native transcript without enforcing translations.

    Appends timestamps to each caption string if include_time is True.
    """
    try:
        api_instance = YouTubeTranscriptApi()
        transcript_list = api_instance.list(video_id)
        # Select the first available default/native script
        transcript = next(iter(transcript_list))
        data = transcript.fetch()

        lines = []
        for item in data:
            if include_time:
                timestamp = format_timestamp(item.start)
                lines.append(f"{timestamp} {item.text}")
            else:
                lines.append(item.text)

        return " ".join(lines)
    except Exception:
        return None


def export_to_pdf(text, file_path, video_title):
    """Generate a formatted ReportLab PDF document containing the transcript."""
    doc = SimpleDocTemplate(
        file_path,
        pagesize=letter,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45,
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        spaceAfter=22,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["BodyText"],
        fontSize=10,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=12,
    )

    story.append(Paragraph(video_title, title_style))
    story.append(Spacer(1, 10))

    # Escape standard HTML characters for ReportLab compatibility
    safe_text = (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    story.append(Paragraph(safe_text, body_style))
    doc.build(story)


# --- GUI APPLICATION CLASS ---


class TranscriptApp:
    """Class responsible for managing the Tkinter GUI interface and threads."""

    def __init__(self, root_window):
        self.root = root_window
        self.root.title("YouTube Transcript Pro")
        self.root.geometry("600x480")
        self.root.resizable(False, False)

        # URL Input Field
        tk.Label(
            root_window, text="YouTube Video or Playlist URL:", font=("Arial", 10, "bold")
        ).pack(pady=10)
        self.entry_url = tk.Entry(root_window, width=70, font=("Arial", 10))
        self.entry_url.pack(pady=5)

        # Timestamps Checkbox
        self.time_checkbox_var = tk.BooleanVar(value=False)
        self.chk_time = tk.Checkbutton(
            root_window,
            text="Include timestamps (e.g., [01:23])",
            variable=self.time_checkbox_var,
            font=("Arial", 9),
        )
        self.chk_time.pack(pady=5)

        # Context Menu (Right-Click Menu) Setup
        self.context_menu = tk.Menu(root_window, tearoff=0)
        self.context_menu.add_command(
            label="Cut", command=lambda: self.entry_url.event_generate("<<Cut>>")
        )
        self.context_menu.add_command(
            label="Copy", command=lambda: self.entry_url.event_generate("<<Copy>>")
        )
        self.context_menu.add_command(
            label="Paste", command=lambda: self.entry_url.event_generate("<<Paste>>")
        )

        # Bind Right-Click context menus across operating systems
        if os.name == "nt" or os.name == "posix":
            self.entry_url.bind("<Button-3>", self.show_context_menu)
        if os.name != "nt":
            self.entry_url.bind("<Button-2>", self.show_context_menu)

        # Action Buttons Layout
        button_frame = tk.Frame(root_window)
        button_frame.pack(pady=10)

        self.btn_convert = tk.Button(
            button_frame,
            text="Convert",
            command=self.start_conversion_thread,
            bg="#cc0000",
            fg="white",
            font=("Arial", 10, "bold"),
            width=12,
        )
        self.btn_convert.pack(side=tk.LEFT, padx=10)

        self.btn_folder = tk.Button(
            button_frame,
            text="Open Folder",
            command=self.open_output_folder,
            font=("Arial", 10),
            width=12,
        )
        self.btn_folder.pack(side=tk.LEFT, padx=10)

        # Activity Terminal Log Box
        tk.Label(
            root_window, text="Activity Log:", font=("Arial", 9, "italic")
        ).pack(anchor="w", padx=20)
        self.log_box = scrolledtext.ScrolledText(
            root_window, width=68, height=14, font=("Consolas", 9), bg="#f4f4f4"
        )
        self.log_box.pack(pady=5, padx=20)
        self.write_to_log("System ready. Awaiting input URL...\n")

    def show_context_menu(self, event):
        """Display the pop-up context menu at the mouse cursor position."""
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def write_to_log(self, text):
        """Append operational tracking texts to the UI terminal area."""
        self.log_box.insert(tk.END, text)
        self.log_box.see(tk.END)

    def start_conversion_thread(self):
        """Initialize worker threads to download assets without locking the UI."""
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Warning", "The URL field cannot be empty.")
            return

        self.btn_convert.config(state="disabled")
        include_time = self.time_checkbox_var.get()

        worker_thread = threading.Thread(
            target=self.process_conversion, args=(url, include_time)
        )
        worker_thread.daemon = True
        worker_thread.start()

    def process_conversion(self, url, include_time):
        """Execute the heavy-lifting scraping and PDF rendering logic."""
        self.write_to_log("Analyzing URL link...\n")
        link_data = parse_link(url)

        time_status = "ENABLED" if include_time else "DISABLED"
        self.write_to_log(f"Timestamps configuration: {time_status}\n")

        # Handle Single Video Entity
        if link_data["type"] == "video":
            title = get_video_title(link_data["id"])
            self.write_to_log(f"Processing video: {title}\n")
            filename = sanitize_filename(title) + ".pdf"

            text = get_native_transcript(link_data["id"], include_time)
            if text:
                export_to_pdf(text, filename, title)
                self.write_to_log(f"[SUCCESS] Saved file as: {filename}\n\n")
                messagebox.showinfo("Done", "Video converted successfully.")
            else:
                self.write_to_log(
                    "[ERROR] Failed to fetch native transcript text.\n\n"
                )
                messagebox.showerror(
                    "Error", "This video doesn't contain default transcripts."
                )

        # Handle Playlist Entity
        elif link_data["type"] == "playlist":
            playlist_title = get_playlist_title(link_data["id"])
            folder_name = sanitize_filename(playlist_title)
            os.makedirs(folder_name, exist_ok=True)

            self.write_to_log(
                f"Playlist detected: {playlist_title}\nFetching videos...\n"
            )
            video_ids = extract_playlist_video_ids(link_data["id"])
            total_count = len(video_ids)
            self.write_to_log(f"Found {total_count} videos in list.\n")

            successful_downloads = 0
            for idx, vid in enumerate(video_ids, 1):
                vid_title = get_video_title(vid)
                self.write_to_log(
                    f"[{idx}/{total_count}] Processing: {vid_title[:40]}...\n"
                )

                vid_filename = sanitize_filename(vid_title) + ".pdf"
                full_path = os.path.join(folder_name, vid_filename)

                vid_text = get_native_transcript(vid, include_time)
                if vid_text:
                    export_to_pdf(vid_text, full_path, vid_title)
                    successful_downloads += 1
                else:
                    self.write_to_log(
                        " -> [SKIPPED] Native transcript missing.\n"
                    )

            self.write_to_log(
                f"\n[DONE] Successfully built {successful_downloads} out of {total_count} PDFs.\n\n"
            )
            messagebox.showinfo(
                "Completed",
                f"Playlist done.\nTarget directory: {folder_name}",
            )

        self.btn_convert.config(state="normal")

    def open_output_folder(self):
        """Cross-platform directory handler to reveal working files location."""
        current_dir = os.getcwd()
        try:
            if os.name == "nt":  # Windows OS
                os.startfile(current_dir)
            elif os.platform == "darwin":  # macOS
                subprocess.Popen(["open", current_dir])
            else:  # Linux OS Distribution
                subprocess.Popen(["xdg-open", current_dir])
        except Exception as e:
            messagebox.showerror("Folder Error", str(e))


if __name__ == "__main__":
    app_root = tk.Tk()
    app_instance = TranscriptApp(app_root)
    app_root.mainloop()