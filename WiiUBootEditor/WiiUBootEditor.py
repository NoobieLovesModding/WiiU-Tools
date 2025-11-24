import os
# Preconfigure a modern, high-DPI friendly look before the real Tk root is created.
try:
    import platform
    from tkinter import Tk, font as tkfont

    tmp_root = Tk()
    tmp_root.withdraw()

    # Attempt sensible scaling for HiDPI displays
    try:
        tmp_root.tk.call('tk', 'scaling', 1.5)
    except Exception:
        pass

    # Pick a modern system font per platform
    sys_plat = platform.system()
    if sys_plat == "Windows":
        family = "Segoe UI"
    elif sys_plat == "Darwin":
        family = "Helvetica Neue"
    else:
        family = "Roboto"

    # Configure default fonts
    default_font = tkfont.nametofont("TkDefaultFont")
    default_font.configure(family=family, size=10)
    tmp_root.option_add("*Font", default_font)

    # Modern color palette (neutral surfaces + vivid accent)
    ACCENT = "#0f62fe"      # vivid blue accent
    ACCENT_HOVER = "#0b5ed7"
    SURFACE = "#f6f7fa"     # light neutral background
    SURFACE_ALT = "#ffffff" # cards / text backgrounds
    TEXT = "#111827"        # primary text
    MUTED = "#6b7280"       # secondary text

    # Apply tasteful defaults to common widgets
    tmp_root.option_add("*Background", SURFACE)
    tmp_root.option_add("*Foreground", TEXT)

    tmp_root.option_add("*Button.Background", ACCENT)
    tmp_root.option_add("*Button.Foreground", "#ffffff")
    tmp_root.option_add("*Button.ActiveBackground", ACCENT_HOVER)

    tmp_root.option_add("*Label.Background", SURFACE)
    tmp_root.option_add("*Label.Foreground", TEXT)

    tmp_root.option_add("*Frame.Background", SURFACE)
    tmp_root.option_add("*Entry.Background", SURFACE_ALT)
    tmp_root.option_add("*Entry.Foreground", TEXT)
    tmp_root.option_add("*Text.Background", SURFACE_ALT)
    tmp_root.option_add("*Text.Foreground", TEXT)

    # subtle default padding via widget-specific options (some Tk builds respect these)
    tmp_root.option_add("*PadX", 8)
    tmp_root.option_add("*PadY", 6)

    tmp_root.update_idletasks()
    tmp_root.destroy()
except Exception:
    # Headless environment or tkinter not available — fail silently and let app continue.
    pass
import sys
import shutil
import subprocess
import threading
import tempfile
import struct
import wave
from pathlib import Path
from tkinter import Tk, Label, Button, filedialog, Text, Toplevel, StringVar, OptionMenu, messagebox, Scrollbar, RIGHT, Y, END, LEFT, BOTH, X, Frame, PhotoImage
from tkinter import simpledialog
import PIL
import imageio_ffmpeg as iioff
import imageio_ffmpeg as iioff
from PIL import Image

# WiiUBootEditor.py
# Minimal professional GUI to convert audio -> .btsnd and images -> .tga
# Creates a simple custom .btsnd wrapper (header + PCM WAV frames).
# Requirements will be auto-installed: pyvgmstream (if missing), pillow, imageio-ffmpeg.


# Ensure pip installs run in same Python
def pip_install(packages):
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + packages
    try:
        subprocess.check_call(cmd)
        return True
    except Exception:
        return False

# Auto-install dependencies if missing
def ensure_dependencies(status_callback=None):
    to_install = []
    # Check Pillow (PIL)
    try:
        import PIL
    except Exception:
        to_install.append("Pillow")
    # Check imageio-ffmpeg
    try:
        import imageio_ffmpeg as _iioff
    except Exception:
        to_install.append("imageio-ffmpeg")
    # Optional helper library pyvgmstream
    try:
        import pyvgmstream  # optional helper library
    except Exception:
        to_install.append("pyvgmstream")
    if to_install:
        if status_callback:
            status_callback("Installing: " + ", ".join(to_install))
        ok = pip_install(to_install)
        if not ok:
            if status_callback:
                status_callback("Automatic install failed. Please install: " + ", ".join(to_install))
            return False
    return True

# Helper: get ffmpeg executable (provided by imageio_ffmpeg or system ffmpeg)
def get_ffmpeg_exe():
    try:
        # prefer system ffmpeg
        subprocess.check_call(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "ffmpeg"
    except Exception:
        try:
            exe = iioff.get_ffmpeg_exe()
            return exe
        except Exception:
            return None

# Conversion routines
def audio_to_btsnd(paths, out_dir, status_callback=None):
    ffmpeg = get_ffmpeg_exe()
    if not ffmpeg:
        if status_callback:
            status_callback("ffmpeg not available.")
        return
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        out_file = Path(out_dir) / (p.stem + ".btsnd")
        if status_callback:
            status_callback(f"Converting audio: {p.name} -> {out_file.name}")
        try:
            # create temporary WAV file with consistent format
            tmp_wav = Path(tempfile.gettempdir()) / (p.stem + "_tmp.wav")
            cmd = [ffmpeg, "-y", "-i", str(p), "-ar", "44100", "-ac", "2", "-vn", "-f", "wav", str(tmp_wav)]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Read WAV and wrap into simple .btsnd container:
            with wave.open(str(tmp_wav), 'rb') as wf:
                nchannels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
            # btsnd header: 5 bytes 'BTSND' + uint32 le sample_rate + uint16 channels + uint16 sampwidth + uint64 data_length
            header = b'BTSND' + struct.pack('<IHHQ', framerate, nchannels, sampwidth, len(frames))
            with open(out_file, 'wb') as f:
                f.write(header)
                f.write(frames)
            tmp_wav.unlink(missing_ok=True)
            if status_callback:
                status_callback(f"Saved: {out_file}")
        except Exception as e:
            if status_callback:
                status_callback(f"Error converting {p.name}: {e}")

def images_to_tga(paths, out_dir, status_callback=None):
    try:
        for p in paths:
            p = Path(p)
            if not p.exists():
                continue
            out_file = Path(out_dir) / (p.stem + ".tga")
            if status_callback:
                status_callback(f"Converting image: {p.name} -> {out_file.name}")
            try:
                img = Image.open(str(p))
                # Convert images with alpha to RGBA, others to RGB
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
                img.save(str(out_file), format="TGA")
                if status_callback:
                    status_callback(f"Saved: {out_file}")
            except Exception as e:
                if status_callback:
                    status_callback(f"Error converting {p.name}: {e}")
    except Exception as e:
        if status_callback:
            status_callback("Pillow not available.")
        return
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        out_file = Path(out_dir) / (p.stem + ".tga")
        if status_callback:
            status_callback(f"Converting image: {p.name} -> {out_file.name}")
        try:
            img = Image.open(str(p))
            # Convert images with alpha to RGBA, others to RGB
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
            img.save(str(out_file), format="TGA")
            if status_callback:
                status_callback(f"Saved: {out_file}")
        except Exception as e:
            if status_callback:
                status_callback(f"Error converting {p.name}: {e}")

# Simple localization
STRINGS = {
    "en": {
        "title": "WiiU Boot Editor - Converter",
        "select_files": "Select Files",
        "convert_audio": "Convert Audio -> .btsnd",
        "convert_images": "Convert Images -> .tga",
        "settings": "Settings",
        "credits": "Credits",
        "update_log": "Update Log",
        "quit": "Quit",
        "status": "Status",
        "install_deps": "Checking/Installing dependencies...",
        "done": "Operation complete.",
        "primary_dev_label": "Primary Developer:",
        "primary_dev_name": "Noobie",
        "theme": "Theme",
        "light": "Light",
        "dark": "Dark",
        "language": "Language",
        "select_output_dir": "Select Output Directory",
        "no_files_selected": "No files selected.",
    },
    "fr": {
        "title": "WiiU Boot Editor - Convertisseur",
        "select_files": "Sélectionner des fichiers",
        "convert_audio": "Convertir audio -> .btsnd",
        "convert_images": "Convertir images -> .tga",
        "settings": "Paramètres",
        "credits": "Crédits",
        "update_log": "Journal des mises à jour",
        "quit": "Quitter",
        "status": "État",
        "install_deps": "Vérification/Installation des dépendances...",
        "done": "Opération terminée.",
        "primary_dev_label": "Développeur principal :",
        "primary_dev_name": "Noobie",
        "theme": "Thème",
        "light": "Clair",
        "dark": "Sombre",
        "language": "Langue",
        "select_output_dir": "Sélectionner le dossier de sortie",
        "no_files_selected": "Aucun fichier sélectionné.",
    },
    "es": {
        "title": "WiiU Boot Editor - Convertidor",
        "select_files": "Seleccionar archivos",
        "convert_audio": "Convertir audio -> .btsnd",
        "convert_images": "Convertir imágenes -> .tga",
        "settings": "Ajustes",
        "credits": "Créditos",
        "update_log": "Registro de actualizaciones",
        "quit": "Salir",
        "status": "Estado",
        "install_deps": "Comprobando/Instalando dependencias...",
        "done": "Operación completada.",
        "primary_dev_label": "Desarrollador principal:",
        "primary_dev_name": "Noobie",
        "theme": "Tema",
        "light": "Claro",
        "dark": "Oscuro",
        "language": "Idioma",
        "select_output_dir": "Seleccionar carpeta de salida",
        "no_files_selected": "No hay archivos seleccionados.",
    }
}

class App:
    def __init__(self, root):
        self.root = root
        self.lang = "en"
        self.str = STRINGS[self.lang]
        self.theme = "light"
        self.selected_files = []
        self.output_dir = str(Path.home())
        root.title(self.str["title"])
        root.geometry("700x420")
        root.resizable(False, False)
        self._build_ui()
        threading.Thread(target=self._init_deps, daemon=True).start()

    def _build_ui(self):
        self.frame_top = Frame(self.root)
        self.frame_top.pack(fill=X, padx=10, pady=10)

        self.btn_select = Button(self.frame_top, text=self.str["select_files"], command=self.select_files, width=20)
        self.btn_select.pack(side=LEFT, padx=5)

        self.btn_audio = Button(self.frame_top, text=self.str["convert_audio"], command=self.convert_audio_thread, width=25)
        self.btn_audio.pack(side=LEFT, padx=5)

        self.btn_image = Button(self.frame_top, text=self.str["convert_images"], command=self.convert_images_thread, width=25)
        self.btn_image.pack(side=LEFT, padx=5)

        self.frame_mid = Frame(self.root)
        self.frame_mid.pack(fill=BOTH, expand=True, padx=10, pady=(0,10))

        # Status log
        lbl = Label(self.frame_mid, text=self.str["status"])
        lbl.pack(anchor="w")
        self.txt_status = Text(self.frame_mid, height=15)
        self.txt_status.pack(fill=BOTH, expand=True, side=LEFT)
        self.scroll = Scrollbar(self.frame_mid, command=self.txt_status.yview)
        self.scroll.pack(side=RIGHT, fill=Y)
        self.txt_status.config(yscrollcommand=self.scroll.set, state='normal')

        # Bottom buttons
        self.frame_bottom = Frame(self.root)
        self.frame_bottom.pack(fill=X, padx=10, pady=10)
        self.btn_settings = Button(self.frame_bottom, text=self.str["settings"], command=self.open_settings)
        self.btn_settings.pack(side=LEFT, padx=5)
        self.btn_credits = Button(self.frame_bottom, text=self.str["credits"], command=self.open_credits)
        self.btn_credits.pack(side=LEFT, padx=5)
        self.btn_updates = Button(self.frame_bottom, text=self.str["update_log"], command=self.open_update_log)
        self.btn_updates.pack(side=LEFT, padx=5)
        self.btn_quit = Button(self.frame_bottom, text=self.str["quit"], command=self.root.quit)
        self.btn_quit.pack(side=RIGHT, padx=5)

        self.apply_theme()

    def log(self, msg):
        self.txt_status.insert(END, str(msg) + "\n")
        self.txt_status.see(END)

    def _init_deps(self):
        self.log(STRINGS[self.lang]["install_deps"])
        ok = ensure_dependencies(status_callback=self.log)
        if not ok:
            self.log("Dependency install failed. Please install required packages manually.")
        else:
            ff = get_ffmpeg_exe()
            self.log(f"ffmpeg: {ff}")
            self.log("Ready.")

    def select_files(self):
        files = filedialog.askopenfilenames(title=self.str["select_files"], initialdir=str(Path.home()))
        if files:
            self.selected_files = list(files)
            self.log(f"Selected {len(files)} files.")
        else:
            self.log(self.str["no_files_selected"])

    def _choose_output_dir(self):
        od = filedialog.askdirectory(title=self.str["select_output_dir"], initialdir=self.output_dir)
        if od:
            self.output_dir = od
        return self.output_dir

    def convert_audio_thread(self):
        if not self.selected_files:
            self.select_files()
            if not self.selected_files:
                return
        out = self._choose_output_dir()
        t = threading.Thread(target=audio_to_btsnd, args=(self.selected_files, out, self.log), daemon=True)
        t.start()

    def convert_images_thread(self):
        if not self.selected_files:
            self.select_files()
            if not self.selected_files:
                return
        out = self._choose_output_dir()
        t = threading.Thread(target=images_to_tga, args=(self.selected_files, out, self.log), daemon=True)
        t.start()

    def open_settings(self):
        win = Toplevel(self.root)
        win.title(self.str["settings"])
        win.geometry("320x160")
        Label(win, text=self.str["theme"]).pack(anchor="w", padx=10, pady=(10,0))
        theme_var = StringVar(win)
        theme_var.set(self.theme)
        def set_theme(val):
            self.theme = val
            self.apply_theme()
        OptionMenu(win, theme_var, "light", "dark", command=set_theme).pack(anchor="w", padx=10)

        Label(win, text=self.str["language"]).pack(anchor="w", padx=10, pady=(10,0))
        lang_var = StringVar(win)
        lang_var.set(self.lang)
        def set_lang(val):
            self.lang = val
            self.str = STRINGS[self.lang]
            self._refresh_ui_texts()
        OptionMenu(win, lang_var, "en", "fr", "es", command=set_lang).pack(anchor="w", padx=10)

    def apply_theme(self):
        if self.theme == "dark":
            bg = "#202124"
            fg = "#e8eaed"
            btn_bg = "#2b2e31"
        else:
            bg = "#f6f6f6"
            fg = "#111111"
            btn_bg = "#eaeaea"
        self.root.configure(bg=bg)
        for w in (self.frame_top, self.frame_mid, self.frame_bottom):
            w.configure(bg=bg)
        for btn in (self.btn_select, self.btn_audio, self.btn_image, self.btn_settings, self.btn_credits, self.btn_updates, self.btn_quit):
            btn.configure(bg=btn_bg, fg=fg, activebackground=btn_bg)
        self.txt_status.configure(bg="#1e1e1e" if self.theme=="dark" else "white", fg=fg)

    def _refresh_ui_texts(self):
        self.root.title(self.str["title"])
        self.btn_select.configure(text=self.str["select_files"])
        self.btn_audio.configure(text=self.str["convert_audio"])
        self.btn_image.configure(text=self.str["convert_images"])
        self.btn_settings.configure(text=self.str["settings"])
        self.btn_credits.configure(text=self.str["credits"])
        self.btn_updates.configure(text=self.str["update_log"])
        self.btn_quit.configure(text=self.str["quit"])

    def open_credits(self):
        win = Toplevel(self.root)
        win.title(self.str["credits"])
        win.geometry("300x120")
        Label(win, text=self.str["primary_dev_label"], font=("Arial", 10, "bold")).pack(anchor="n", pady=(10,0))
        Label(win, text=self.str["primary_dev_name"], font=("Arial", 12)).pack(anchor="n", pady=(5,10))

    def open_update_log(self):
        win = Toplevel(self.root)
        win.title(self.str["update_log"])
        win.geometry("480x320")
        Label(win, text=self.str["update_log"], font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10,0))
        txt = Text(win)
        txt.pack(fill=BOTH, expand=True, padx=10, pady=10)
        # Example planned updates - user can edit
        sample = ("v0.1 - Initial release: audio -> .btsnd, images -> .tga\n"
                  "Planned:\n - Drag & drop support\n - Presets for encoding\n - Improved .btsnd format compatibility\n - Batch queue UI\n")
        txt.insert(END, sample)
        def save_log():
            path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(txt.get("1.0", END))
                messagebox.showinfo("Saved", "Update log saved.")
        Button(win, text="Save", command=save_log).pack(side=LEFT, padx=10, pady=(0,10))

def main():
    root = Tk()
    app = App(root)
    # Add drag and drop support now that root and app exist
    try:
        root.tk.call("package", "require", "tkdnd")
        def drop(event):
            files = root.tk.splitlist(event.data)
            app.selected_files.extend(files)
            app.log(f"Selected {len(files)} files via drag and drop.")
        root.tk.createcommand("::tkdnd::drop", drop)
    except Exception:
        # tkdnd not available or setup failed; continue without drag-drop
        pass
    root.mainloop()

if __name__ == "__main__":
    if __name__ == "__main__":
        # Override App.open_update_log to include the requested line in the sample text
        def _open_update_log(self):
            win = Toplevel(self.root)
            win.title(self.str["update_log"])
            win.geometry("480x320")
            Label(win, text=self.str["update_log"], font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10,0))
            txt = Text(win)
            txt.pack(fill=BOTH, expand=True, padx=10, pady=10)
            sample = ("v0.1 - Initial release: audio -> .btsnd, images -> .tga\n"
                      "Planned:\n - Drag & drop support\n - Presets for encoding\n - Improved .btsnd format compatibility\n - Batch queue UI\n"
                      "I plan on adding Ftp support to the app!\n")
            txt.insert(END, sample)
            def save_log():
                path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
                if path:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(txt.get("1.0", END))
                    messagebox.showinfo("Saved", "Update log saved.")
            Button(win, text="Save", command=save_log).pack(side=LEFT, padx=10, pady=(0,10))

        App.open_update_log = _open_update_log
        # create a dedicated app directory for converted files and the app icon, then start app

        # Determine platform-appropriate app directory
        if sys.platform.startswith("win"):
            base = Path(os.getenv("APPDATA") or Path.home())
            APP_DIR = base / "WiiUBootEditor"
        elif sys.platform == "darwin":
            APP_DIR = Path.home() / "Library" / "Application Support" / "WiiUBootEditor"
        else:
            APP_DIR = Path.home() / ".local" / "share" / "WiiUBootEditor"

        ICON_DIR = APP_DIR / "icons"
        CONVERTED_DIR = APP_DIR / "converted"
        IMAGES_DIR = CONVERTED_DIR / "images"
        AUDIO_DIR = CONVERTED_DIR / "audio"

        for d in (APP_DIR, ICON_DIR, CONVERTED_DIR, IMAGES_DIR, AUDIO_DIR):
            d.mkdir(parents=True, exist_ok=True)

        # Create a simple app icon if none exists
        icon_path = ICON_DIR / "app_icon.png"
        if not icon_path.exists():
            try:
                img = Image.new("RGBA", (64, 64), (30, 144, 255, 255))
                # subtle diagonal stripe
                for i in range(0, 64, 4):
                    for j in range(64):
                        if (i + j) % 8 == 0:
                            img.putpixel((i, j), (255, 255, 255, 40))
                img.save(icon_path)
            except Exception:
                pass

        # Monkey-patch App.__init__ to set default output dir and apply the app icon
        _original_init = App.__init__
        def _patched_init(self, root, *args, **kwargs):
            _original_init(self, root, *args, **kwargs)
            # set app default output dir to our converted folder
            try:
                self.output_dir = str(CONVERTED_DIR)
            except Exception:
                pass
        # Start app
        main()
        # Start app
        # Add drag and drop support
        def drop(event):
            files = root.tk.splitlist(event.data)
            self.selected_files.extend(files)
            self.log(f"Selected {len(files)} files via drag and drop.")

        root.tk.call("package", "require", "tkdnd")
        root.tk.createcommand("::tkdnd::drop", drop)

        main()