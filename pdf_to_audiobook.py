#!/usr/bin/env python3
"""
PDF to Audiobook Converter - Single-file Tkinter app

Features:
- Load PDF, extract text using PyMuPDF (fitz)
- Offline TTS via pyttsx3 (save_to_file) OR online via gTTS
- Export to MP3, play MP3 inside app (pygame)
- Controls: speech rate, chunk size, choose page range
- Simple logging and progress updates

Save this as pdf_to_audiobook.py and run: python pdf_to_audiobook.py
"""

import os
import threading
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz  # PyMuPDF
import pyttsx3
from gtts import gTTS
import pygame
import time
import re

# ---------- Utility functions ----------
def clean_text(s: str) -> str:
    # remove multiple newlines and excessive spaces
    s = re.sub(r'\n\s*\n+', '\n\n', s)
    s = s.replace('\x0c', '')  # form feed
    s = s.strip()
    return s

def extract_text_from_pdf(path, start_page=None, end_page=None, log=None):
    doc = fitz.open(path)
    start_page = 0 if start_page is None else max(0, start_page)
    end_page = doc.page_count - 1 if end_page is None else min(doc.page_count - 1, end_page)
    all_text = []
    for i in range(start_page, end_page + 1):
        page = doc.load_page(i)
        text = page.get_text().strip()
        if text:
            cleaned = clean_text(text)
            all_text.append((i + 1, cleaned))
            if log:
                log(f"Page {i+1}: {len(cleaned)} chars")
        else:
            if log:
                log(f"Page {i+1}: (empty) skipped")
    doc.close()
    return all_text

# ---------- TTS handling ----------
class TTSManager:
    def __init__(self, engine_name='pyttsx3'):
        self.engine_name = engine_name
        if engine_name == 'pyttsx3':
            self.engine = pyttsx3.init()
            # collect voices metadata
            self.voices = self.engine.getProperty('voices')
        else:
            self.engine = None
            self.voices = []

    def get_voice_names(self):
        if self.engine_name == 'pyttsx3':
            return [v.name for v in self.voices]
        return []

    def set_rate(self, rate):
        if self.engine_name == 'pyttsx3':
            self.engine.setProperty('rate', rate)

    def set_volume(self, volume):
        # volume in pyttsx3 is 0.0-1.0
        if self.engine_name == 'pyttsx3':
            self.engine.setProperty('volume', max(0.0, min(1.0, volume)))

    def set_voice_by_index(self, idx):
        if self.engine_name == 'pyttsx3' and 0 <= idx < len(self.voices):
            self.engine.setProperty('voice', self.voices[idx].id)

    def save_text_to_mp3_pyttsx3(self, text, out_path, log=None):
        """Use pyttsx3 to save to file. Blocking call (but run in thread outside)."""
        if self.engine_name != 'pyttsx3':
            raise RuntimeError("pyttsx3 engine not initialized")
        if log: log("pyttsx3: starting save_to_file ...")
        self.engine.save_to_file(text, out_path)
        self.engine.runAndWait()
        if log: log(f"Saved (pyttsx3) -> {out_path}")

    def save_text_to_mp3_gtts(self, text, out_path, lang='en', log=None):
        """Use gTTS to generate mp3. Requires internet."""
        if log: log("gTTS: generating audio...")
        tts = gTTS(text=text, lang=lang)
        tts.save(out_path)
        if log: log(f"Saved (gTTS) -> {out_path}")

# ---------- Playback ----------
class Player:
    def __init__(self, log=None):
        pygame.mixer.init()
        self.current = None
        self.paused = False
        self.log = log

    def play(self, filepath):
        if not os.path.isfile(filepath):
            if self.log: self.log("Play: file not found")
            return
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            self.current = filepath
            if self.log: self.log(f"Playing {os.path.basename(filepath)}")
        except Exception as e:
            if self.log: self.log(f"Play error: {e}")

    def stop(self):
        pygame.mixer.music.stop()
        self.current = None
        if self.log: self.log("Stopped")

    def pause(self):
        if not self.paused:
            pygame.mixer.music.pause()
            self.paused = True
            if self.log: self.log("Paused")
        else:
            pygame.mixer.music.unpause()
            self.paused = False
            if self.log: self.log("Resumed")

# ---------- GUI ----------
class PDFToAudiobookApp:
    def __init__(self, root):
        self.root = root
        root.title("PDF → Audiobook")
        root.geometry("820x600")
        self.pdf_path = None
        self.extracted = []  # list of (page_no, text)
        self.tempdir = tempfile.mkdtemp(prefix="pdf_audiobook_")
        self.player = Player(log=self.log)
        self.tts_manager = TTSManager('pyttsx3')  # default
        self.setup_ui()

    def setup_ui(self):
        frm = ttk.Frame(self.root, padding=8)
        frm.pack(fill='both', expand=True)

        # Top controls
        top = ttk.Frame(frm)
        top.pack(fill='x', pady=4)

        ttk.Button(top, text="Load PDF", command=self.load_pdf).pack(side='left')
        ttk.Button(top, text="Create Sample PDF", command=self.create_sample_pdf).pack(side='left', padx=6)

        ttk.Label(top, text="TTS Engine:").pack(side='left', padx=(10,2))
        self.engine_var = tk.StringVar(value='pyttsx3')
        engine_menu = ttk.Combobox(top, textvariable=self.engine_var, values=['pyttsx3', 'gTTS'], width=8)
        engine_menu.pack(side='left')
        engine_menu.bind("<<ComboboxSelected>>", lambda e: self.change_engine())

        ttk.Label(top, text="Rate:").pack(side='left', padx=(10,2))
        self.rate_var = tk.IntVar(value=160)
        ttk.Spinbox(top, from_=80, to=300, textvariable=self.rate_var, width=6).pack(side='left')

        ttk.Label(top, text="Chunk size (chars):").pack(side='left', padx=(10,2))
        self.chunk_var = tk.IntVar(value=3500)
        ttk.Spinbox(top, from_=1000, to=15000, increment=500, textvariable=self.chunk_var, width=7).pack(side='left')

        # Page range options
        range_frame = ttk.Frame(frm)
        range_frame.pack(fill='x', pady=6)
        ttk.Label(range_frame, text="Pages (start-end, leave blank = all):").pack(side='left')
        self.pages_entry = ttk.Entry(range_frame, width=20)
        self.pages_entry.pack(side='left', padx=6)

        # Main area: left list of pages, right controls + log
        main = ttk.Panedwindow(frm, orient='horizontal')
        main.pack(fill='both', expand=True)

        left = ttk.Frame(main, width=280)
        main.add(left, weight=1)
        right = ttk.Frame(main)
        main.add(right, weight=3)

        ttk.Label(left, text="Extracted pages").pack(anchor='w')
        self.pages_list = tk.Listbox(left, height=20)
        self.pages_list.pack(fill='both', expand=True, padx=4, pady=4)

        # Right controls
        controls = ttk.Frame(right)
        controls.pack(fill='x', pady=4)
        ttk.Button(controls, text="Extract Text", command=self.extract_clicked).pack(side='left')
        ttk.Button(controls, text="Convert -> MP3", command=self.convert_clicked).pack(side='left', padx=6)
        ttk.Button(controls, text="Play Selected MP3", command=self.play_selected_mp3).pack(side='left', padx=6)
        ttk.Button(controls, text="Stop", command=lambda: self.player.stop()).pack(side='left', padx=6)
        ttk.Button(controls, text="Pause/Resume", command=lambda: self.player.pause()).pack(side='left', padx=6)

        # Log / details
        ttk.Label(right, text="Log / Output").pack(anchor='w')
        self.log_text = tk.Text(right, height=20)
        self.log_text.pack(fill='both', expand=True, padx=4, pady=4)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief='sunken', anchor='w').pack(side='bottom', fill='x')

    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert('end', f"[{ts}] {msg}\n")
        self.log_text.see('end')
        self.status_var.set(msg)

    def change_engine(self):
        eng = self.engine_var.get()
        self.tts_manager = TTSManager(eng)
        self.log(f"Switched TTS engine -> {eng}")
        # update rate/voice options if pyttsx3
        if eng == 'pyttsx3':
            voices = self.tts_manager.get_voice_names()
            self.log(f"Available voices: {voices[:5]}{'...' if len(voices)>5 else ''}")

    def load_pdf(self):
        path = filedialog.askopenfilename(title="Select PDF", filetypes=[("PDF files","*.pdf")])
        if not path:
            return
        self.pdf_path = path
        self.log(f"Selected PDF: {path}")
        self.root.title(f"PDF → Audiobook — {os.path.basename(path)}")

    def create_sample_pdf(self):
        # create a simple 3-page sample PDF using fitz
        sample_path = os.path.join(self.tempdir, "sample.pdf")
        doc = fitz.open()
        for i in range(1,4):
            page = doc.new_page()
            text = f"Sample PDF page {i}\n\nThis is a sample page to demo PDF to audiobook conversion.\n" * 6
            page.insert_text((72, 72), text, fontsize=12)
        doc.save(sample_path)
        doc.close()
        messagebox.showinfo("Sample PDF created", f"Sample PDF saved to:\n{sample_path}")
        self.log(f"Sample PDF created: {sample_path}")

    def extract_clicked(self):
        if not self.pdf_path:
            messagebox.showwarning("No PDF", "Please load a PDF first.")
            return
        # parse page range
        pr = self.pages_entry.get().strip()
        start_page = None
        end_page = None
        if pr:
            try:
                parts = pr.split('-')
                if len(parts) == 2:
                    start_page = int(parts[0]) - 1
                    end_page = int(parts[1]) - 1
                else:
                    start_page = int(parts[0]) - 1
                    end_page = start_page
            except Exception as e:
                messagebox.showerror("Invalid range", "Enter pages like '1-5' or '3'")
                return
        # extract in background thread
        def job():
            try:
                self.pages_list.delete(0, 'end')
                self.extracted = extract_text_from_pdf(self.pdf_path, start_page, end_page, log=self.log)
                for p, text in self.extracted:
                    preview = text[:120].replace('\n',' ')
                    self.pages_list.insert('end', f"Page {p}: {preview}...")
                self.log(f"Extraction complete — {len(self.extracted)} pages")
            except Exception as e:
                self.log(f"Extraction error: {e}")
        threading.Thread(target=job, daemon=True).start()

    def convert_clicked(self):
        if not self.extracted:
            messagebox.showwarning("No text", "No extracted text. Click 'Extract Text' first.")
            return
        engine = self.engine_var.get()
        rate = self.rate_var.get()
        chunk_size = self.chunk_var.get()

        # choose output path
        outdir = filedialog.askdirectory(title="Choose folder to save MP3(s)")
        if not outdir:
            return

        def job():
            self.log("Starting conversion...")
            if engine == 'pyttsx3':
                # configure manager
                self.tts_manager.set_rate(rate)
                # volume handled by engine if desired; leave default
            # For each page create one MP3 (or chunk them as desired)
            for page_no, text in self.extracted:
                # split into chunks if too big
                chunks = []
                if len(text) <= chunk_size:
                    chunks = [text]
                else:
                    # naive chunking by sentences / words
                    start = 0
                    while start < len(text):
                        end = min(start + chunk_size, len(text))
                        # try not to cut in the middle of a word
                        if end < len(text):
                            next_space = text.rfind(' ', start, end)
                            if next_space > start:
                                end = next_space
                        chunks.append(text[start:end])
                        start = end
                # combine chunks to one file per page
                out_path = os.path.join(outdir, f"page_{page_no}.mp3")
                try:
                    if engine == 'pyttsx3':
                        # pyttsx3 supports saving full text to mp3 (blocking)
                        full_text = "\n\n".join(chunks)
                        self.log(f"Saving page {page_no} via pyttsx3 -> {out_path}")
                        self.tts_manager.save_text_to_mp3_pyttsx3(full_text, out_path, log=self.log)
                    else:
                        # gTTS: must create single mp3 per page by concatenating chunks
                        # We'll generate chunks and append (gTTS only creates files; simple approach: stitch using pygame mixer by playing sequentially)
                        # But to produce a single mp3 file we save chunk mp3s and then combine bytes (naive). Instead we save a single gTTS file per page (by joining chunks with spaces).
                        combined = " ".join(chunks)
                        self.log(f"Saving page {page_no} via gTTS -> {out_path}")
                        self.tts_manager.save_text_to_mp3_gtts(combined, out_path, log=self.log)
                    self.log(f"Page {page_no} exported: {out_path}")
                except Exception as e:
                    self.log(f"Error saving page {page_no}: {e}")
            self.log("Conversion finished.")
            messagebox.showinfo("Done", f"Exported MP3 files to:\n{outdir}")

        threading.Thread(target=job, daemon=True).start()

    def play_selected_mp3(self):
        path = filedialog.askopenfilename(title="Select MP3 to play", filetypes=[("MP3 files","*.mp3")])
        if not path:
            return
        self.player.play(path)

# ---------- Run ----------
def main():
    root = tk.Tk()
    app = PDFToAudiobookApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
