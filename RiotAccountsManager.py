import json
import os
import sys
import subprocess
import time
import ctypes
import ctypes.wintypes
import hashlib
import threading
import winreg
import pyautogui
import pyperclip
import pygetwindow as gw
import requests
from cryptography.fernet import Fernet
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QWizard, QWizardPage, QVBoxLayout, QHBoxLayout,
    QPushButton, QInputDialog, QMessageBox, QComboBox, QLineEdit, QCheckBox,
    QDialog, QLabel, QFileDialog, QProgressBar, QSystemTrayIcon, QMenu,
    QFrame, QScrollArea, QSizePolicy, QDoubleSpinBox
)
from functools import partial

# ─── Costanti ────────────────────────────────────────────────────────────────

APP_NAME        = "RiotAccountsManager By Gabry"
APP_VERSION     = "0.0.4"
GITHUB_REPO     = "Gabryhh/League-Of-Legends-Cred-Manager-"
GITHUB_API_URL  = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

KEY_FILE        = os.path.join(os.environ.get("APPDATA", "."), "RiotAccountsManager", "key.key")
DATA_FILE       = os.path.join(os.environ.get("APPDATA", "."), "RiotAccountsManager", "accounts.enc")
CONFIG_FILE     = os.path.join(os.environ.get("APPDATA", "."), "RiotAccountsManager", "config.json")

# Crea la cartella AppData se non esiste
os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)

DEFAULT_RIOT_PATH = "C:\\Riot Games\\Riot Client\\RiotClientServices.exe"

def resource_path(relative):
    """Restituisce il path corretto sia in sviluppo che nell'exe PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)

APP_ICON = resource_path("info/ico/256x256.ico")

# ─── Config ──────────────────────────────────────────────────────────────────

def default_config():
    return {
        "setup_done": False,
        "riot_client_path": "",
        "coords_username": [420, 506],
        "coords_password": [421, 585],
        "master_password_hash": "",
        "login_delay": 3.0,
        "version": APP_VERSION
    }

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return default_config()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Merge con default per campi mancanti
    cfg = default_config()
    cfg.update(data)
    return cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

# ─── Crittografia account ─────────────────────────────────────────────────────

def generate_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)

def load_key():
    with open(KEY_FILE, "rb") as f:
        return f.read()

def encrypt_data(data):
    cipher = Fernet(load_key())
    return cipher.encrypt(json.dumps(data).encode())

def decrypt_data():
    if not os.path.exists(DATA_FILE):
        return {}
    cipher = Fernet(load_key())
    with open(DATA_FILE, "rb") as f:
        return json.loads(cipher.decrypt(f.read()).decode())

def save_accounts(accounts):
    with open(DATA_FILE, "wb") as f:
        f.write(encrypt_data(accounts))

# ─── Master password ──────────────────────────────────────────────────────────

def hash_master_password(password: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), b"riotaccmgr_salt", 200_000
    ).hex()

def verify_master_password(password: str, stored_hash: str) -> bool:
    return hash_master_password(password) == stored_hash

# ─── Utilità Windows ──────────────────────────────────────────────────────────

def get_monitor_rect_at(x, y):
    user32 = ctypes.windll.user32
    MONITOR_DEFAULTTONEAREST = 0x00000002
    hmon = user32.MonitorFromPoint(ctypes.wintypes.POINT(x, y), MONITOR_DEFAULTTONEAREST)

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize",    ctypes.c_ulong),
            ("rcMonitor", ctypes.wintypes.RECT),
            ("rcWork",    ctypes.wintypes.RECT),
            ("dwFlags",   ctypes.c_ulong),
        ]

    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(hmon, ctypes.byref(info))
    r = info.rcMonitor
    return (r.left, r.top, r.right, r.bottom)

def find_riot_client():
    """Cerca il Riot Client nel percorso default e nel registro di Windows."""
    if os.path.exists(DEFAULT_RIOT_PATH):
        return DEFAULT_RIOT_PATH
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Riot Games\Riot Client")
        path, _ = winreg.QueryValueEx(key, "InstallLocation")
        candidate = os.path.join(path, "RiotClientServices.exe")
        if os.path.exists(candidate):
            return candidate
    except Exception:
        pass
    return ""

# ─── Processi Riot ────────────────────────────────────────────────────────────

def close_riot_processes():
    for name in ["RiotClientServices.exe", "RiotClientUx.exe", "RiotClientUxRender.exe",
                 "LeagueClient.exe", "LeagueClientUx.exe", "League of Legends.exe",
                 "VALORANT.exe", "VALORANT-Win64-Shipping.exe"]:
        try:
            subprocess.run(["taskkill", "/F", "/IM", name],
                           capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception:
            pass
    time.sleep(3)

# ─── Logica avvio account ─────────────────────────────────────────────────────

def select_account(username, accounts, game, config):
    user = accounts.get(username)
    if not user:
        return

    close_riot_processes()

    game_mapping = {
        "League of Legends": "league_of_legends",
        "Valorant": "valorant"
    }

    riot_path = config.get("riot_client_path", DEFAULT_RIOT_PATH)
    subprocess.Popen([
        riot_path,
        f"--launch-product={game_mapping.get(game, 'league_of_legends')}",
        "--launch-patchline=live"
    ])

    # Minimizza le finestre sul monitor primario
    time.sleep(0.3)
    primary_mon = get_monitor_rect_at(0, 0)
    for win in gw.getAllWindows():
        if not win.visible or win.isMinimized or not win.title.strip():
            continue
        try:
            wcx = win.left + win.width  // 2
            wcy = win.top  + win.height // 2
            if primary_mon[0] <= wcx < primary_mon[2] and primary_mon[1] <= wcy < primary_mon[3]:
                win.minimize()
        except Exception:
            pass

    # Attende la finestra del Riot Client visibile e non minimizzata
    timeout = 60
    poll   = 0.5
    elapsed = 0
    riot_window = None
    while elapsed < timeout:
        wins = gw.getWindowsWithTitle("Riot Client")
        if wins and wins[0].visible and not wins[0].isMinimized:
            riot_window = wins[0]
            break
        time.sleep(poll)
        elapsed += poll

    if riot_window is None:
        return

    riot_window.activate()
    time.sleep(config.get("login_delay", 3.0))

    cx, cy = config["coords_username"]
    px, py = config["coords_password"]

    pyautogui.click(cx, cy)
    time.sleep(0.5)
    pyperclip.copy(user["login"])
    pyautogui.hotkey("ctrl", "v")

    pyautogui.click(px, py)
    time.sleep(0.5)
    pyperclip.copy(user["password"])
    pyautogui.hotkey("ctrl", "v")

    pyautogui.press("enter")

# ─── Aggiornamenti automatici ─────────────────────────────────────────────────

class UpdateChecker(QObject):
    update_available = Signal(str, str)  # (versione, download_url)

    def check(self):
        try:
            r = requests.get(GITHUB_API_URL, timeout=5)
            data = r.json()
            latest = data.get("tag_name", "").lstrip("v").lstrip(".")
            if latest and latest != APP_VERSION:
                # Cerca un asset .exe
                url = ""
                for asset in data.get("assets", []):
                    if asset["name"].endswith(".exe"):
                        url = asset["browser_download_url"]
                        break
                if url:
                    self.update_available.emit(latest, url)
        except Exception:
            pass

class DownloadThread(QThread):
    progress = Signal(int)
    finished = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self._dest = os.path.join(
            os.environ.get("APPDATA", "C:\\Users\\Public"),
            "RiotAccountsManager", "update_setup.exe"
        )

    def run(self):
        try:
            os.makedirs(os.path.dirname(self._dest), exist_ok=True)
            r = requests.get(self.url, stream=True, timeout=120)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(self._dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self.progress.emit(int(downloaded * 100 / total))
            self.finished.emit(self._dest)
        except Exception as e:
            self.finished.emit(f"ERROR:{e}")

def show_update_dialog(parent, version, url):
    msg = QMessageBox(parent)
    msg.setWindowTitle("Aggiornamento disponibile")
    msg.setText(f"È disponibile la versione <b>v{version}</b>.<br>Vuoi scaricarla adesso?")
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg.setDefaultButton(QMessageBox.Yes)
    if msg.exec() != QMessageBox.Yes:
        return

    dlg = QDialog(parent)
    dlg.setWindowTitle("Download in corso...")
    dlg.setMinimumWidth(350)
    layout = QVBoxLayout(dlg)
    bar = QProgressBar()
    bar.setRange(0, 100)
    layout.addWidget(QLabel("Download aggiornamento..."))
    layout.addWidget(bar)
    dlg.show()

    # Teniamo il thread come attributo del dialog per evitare garbage collection
    dlg._thread = DownloadThread(url)
    dlg._thread.progress.connect(bar.setValue)

    def on_finished(path):
        dlg.close()
        if not path or path.startswith("ERROR:"):
            err = path.replace("ERROR:", "") if path else "nessun path"
            QMessageBox.critical(parent, "Errore download", f"Dettaglio:\n{err}")
            return
        if not os.path.exists(path):
            QMessageBox.critical(parent, "Errore", f"File non trovato:\n{path}")
            return
        subprocess.Popen(
            [path, "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        QApplication.quit()

    dlg._thread.finished.connect(on_finished)
    dlg._thread.start()

# ─── Setup Wizard ─────────────────────────────────────────────────────────────

class WizardPageWelcome(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Benvenuto in " + APP_NAME)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "<b>Ciao! Prima di iniziare configuriamo tutto in pochi passi.</b><br><br>"
            "Questo wizard ti guiderà nella configurazione iniziale:<br>"
            "• Impostare una <b>master password</b> per il recupero credenziali<br>"
            "• Trovare il percorso di <b>Riot Client</b><br>"
            "• Calibrare i <b>campi di login</b><br>"
            "• Aggiungere il tuo <b>primo account</b><br><br>"
            "Clicca <b>Avanti</b> per iniziare."
        ))

class WizardPageMasterPassword(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Master Password")
        self.setSubTitle(
            "Questa password ti permetterà di vedere le credenziali in chiaro "
            "in caso di recupero. Non viene richiesta ad ogni avvio."
        )
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Master password:"))
        self.pw1 = QLineEdit()
        self.pw1.setEchoMode(QLineEdit.Password)
        self.pw1.setPlaceholderText("Inserisci la master password")
        layout.addWidget(self.pw1)

        layout.addWidget(QLabel("Conferma master password:"))
        self.pw2 = QLineEdit()
        self.pw2.setEchoMode(QLineEdit.Password)
        self.pw2.setPlaceholderText("Ripeti la master password")
        layout.addWidget(self.pw2)

        self.show_cb = QCheckBox("Mostra password")
        self.show_cb.stateChanged.connect(self._toggle)
        layout.addWidget(self.show_cb)

        self.err_label = QLabel("")
        self.err_label.setStyleSheet("color: red;")
        layout.addWidget(self.err_label)

        self.registerField("master_password*", self.pw1)

    def _toggle(self, state):
        mode = QLineEdit.Normal if state else QLineEdit.Password
        self.pw1.setEchoMode(mode)
        self.pw2.setEchoMode(mode)

    def validatePage(self):
        if len(self.pw1.text()) < 4:
            self.err_label.setText("La password deve essere di almeno 4 caratteri.")
            return False
        if self.pw1.text() != self.pw2.text():
            self.err_label.setText("Le password non coincidono.")
            return False
        self.err_label.setText("")
        return True

class WizardPageRiotPath(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Percorso Riot Client")
        self.setSubTitle("Verifichiamo dove è installato il Riot Client sul tuo PC.")
        layout = QVBoxLayout(self)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Percorso RiotClientServices.exe")
        layout.addWidget(self.path_edit)

        browse_btn = QPushButton("Sfoglia...")
        browse_btn.clicked.connect(self._browse)
        layout.addWidget(browse_btn)

        self.err_label = QLabel("")
        self.err_label.setStyleSheet("color: red;")
        layout.addWidget(self.err_label)

        self.registerField("riot_path*", self.path_edit)

    def initializePage(self):
        found = find_riot_client()
        if found:
            self.path_edit.setText(found)
            self.status_label.setText("✅ Riot Client trovato automaticamente.")
        else:
            self.status_label.setText("⚠️ Riot Client non trovato. Seleziona manualmente il percorso.")

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona RiotClientServices.exe",
            "C:\\Riot Games", "Eseguibili (*.exe)"
        )
        if path:
            self.path_edit.setText(path)

    def validatePage(self):
        path = self.path_edit.text().strip()
        if not os.path.exists(path):
            self.err_label.setText("Il percorso selezionato non esiste.")
            return False
        if not path.endswith(".exe"):
            self.err_label.setText("Seleziona un file .exe valido.")
            return False
        self.err_label.setText("")
        return True

class WizardPageCalibration(QWizardPage):
    # Signal emesso dal thread pynput al thread UI
    _coord_captured = Signal(str, int, int)

    def __init__(self):
        super().__init__()
        self.setTitle("Calibrazione campi di login")
        self.setSubTitle(
            "Apriremo il Riot Client. Quando appare la schermata di login, "
            "posiziona il mouse sui campi e premi F8 per salvare la posizione.\n"
            "⚠️ Non spostare il Riot Client dopo l'apertura."
        )
        self._coords_user = None
        self._coords_pass = None
        self._listener    = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        self.launch_btn = QPushButton("1. Avvia Riot Client per la calibrazione")
        self.launch_btn.setMinimumHeight(38)
        self.launch_btn.clicked.connect(self._launch_riot)
        layout.addWidget(self.launch_btn)

        # --- Sezione calibrazione USERNAME ---
        self.user_btn = QPushButton("2. Clicca qui, poi clicca sul campo USERNAME nel Riot Client")
        self.user_btn.setMinimumHeight(38)
        self.user_btn.setEnabled(False)
        self.user_btn.clicked.connect(lambda: self._start_capture("username"))
        layout.addWidget(self.user_btn)

        self.user_pos_label = QLabel("")
        layout.addWidget(self.user_pos_label)

        # --- Sezione calibrazione PASSWORD ---
        self.pass_btn = QPushButton("3. Clicca qui, poi clicca sul campo PASSWORD nel Riot Client")
        self.pass_btn.setMinimumHeight(38)
        self.pass_btn.setEnabled(False)
        self.pass_btn.clicked.connect(lambda: self._start_capture("password"))
        layout.addWidget(self.pass_btn)

        layout.addSpacing(8)

        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setContentsMargins(0, 4, 0, 4)
        layout.addWidget(self.result_label)

        self.redo_btn = QPushButton("🔄 Ripeti calibrazione")
        self.redo_btn.setMinimumHeight(38)
        self.redo_btn.setVisible(False)
        self.redo_btn.clicked.connect(self._reset_calibration)
        layout.addWidget(self.redo_btn)

        layout.addStretch()

        self.err_label = QLabel("")
        self.err_label.setWordWrap(True)
        self.err_label.setStyleSheet("color: red;")
        layout.addWidget(self.err_label)

        # Timer che aggiorna le coordinate del mouse in tempo reale
        self._capturing = None  # "username" o "password"
        self._coord_captured.connect(self._on_coord_captured)

    def _launch_riot(self):
        riot_path = self.wizard().field("riot_path")
        if not riot_path or not os.path.exists(riot_path):
            self.err_label.setText("Percorso Riot Client non valido.")
            return
        try:
            _log("1. launch start")
            # Durante la calibrazione non chiudiamo i processi Riot
            # per evitare crash con psutil su exe con UAC
            subprocess.Popen([riot_path, "--launch-product=league_of_legends", "--launch-patchline=live"])
            _log("2. subprocess done")

            # Sposta il wizard in alto a destra
            screen = QApplication.primaryScreen().geometry()
            wiz = self.wizard()
            wiz.move(screen.right() - wiz.width() - 10, screen.top() + 10)
            wiz.activateWindow()
            wiz.raise_()
            _log("3. wizard moved")

            self.launch_btn.setEnabled(False)
            self.launch_btn.setText("✅ Riot Client avviato")
            self.user_btn.setEnabled(True)
            self._capturing = "username"
            self.err_label.setText("")
            _log("4. buttons updated")

            # Aspetta che il Riot Client sia visibile poi riporta il wizard in primo piano
            def _wait_and_refocus():
                timeout, poll, elapsed = 60, 0.5, 0
                _log("6. wait_and_refocus thread started")
                while elapsed < timeout:
                    try:
                        wins = gw.getWindowsWithTitle("Riot Client")
                        if wins and wins[0].visible and not wins[0].isMinimized:
                            break
                    except Exception:
                        pass
                    time.sleep(poll)
                    elapsed += poll
                _log("7. riot window found, refocusing")
                wiz.activateWindow()
                wiz.raise_()
                _log("5. refocus done")

            threading.Thread(target=_wait_and_refocus, daemon=True).start()

        except Exception as e:
            import traceback
            log_path = os.path.join(os.path.dirname(sys.executable), "crash_log.txt")
            with open(log_path, "w") as f:
                f.write(traceback.format_exc())
            self.err_label.setText(f"Errore: {e}\nLog salvato in: {log_path}")

    def _on_coord_captured(self, field, x, y):
        _log(f"10. on_coord_captured {field} {x},{y}")
        if field == "username":
            self._coords_user = (x, y)
            self.user_btn.setText(f"✅ USERNAME: ({x}, {y})")
            self.pass_btn.setEnabled(True)
        else:
            self._coords_pass = (x, y)
            self.pass_btn.setText(f"✅ PASSWORD: ({x}, {y})")
            self._update_result()
        _log(f"11. on_coord_captured done {field}")

    def _update_mouse_pos(self):
        pass  # non usato

    def _save_position(self, field):
        pass  # non usato

    def _start_capture(self, field):
        if field == "username":
            self.user_btn.setText("⏳ In ascolto... clicca sul campo USERNAME nel Riot Client")
            self.user_btn.setEnabled(False)
        else:
            self.pass_btn.setText("⏳ In ascolto... clicca sul campo PASSWORD nel Riot Client")
            self.pass_btn.setEnabled(False)

        def wait_click():
            _log(f"6. wait_click started for {field}")
            # Aspetta che il bottone venga rilasciato prima di iniziare
            while ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                time.sleep(0.05)
            _log(f"7. button released, waiting for next click")
            # Poi aspetta il prossimo click sinistro
            while True:
                if ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                    pt = ctypes.wintypes.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    _log(f"8. click captured at {pt.x},{pt.y}")
                    self._coord_captured.emit(field, pt.x, pt.y)
                    _log(f"9. signal emitted")
                    break
                time.sleep(0.01)

        threading.Thread(target=wait_click, daemon=True).start()

    def _update_result(self):
        if self._coords_user and self._coords_pass:
            self.result_label.setText(
                f"✅ Calibrazione completata!\n"
                f"Username: {self._coords_user}   Password: {self._coords_pass}"
            )
            self.redo_btn.setVisible(True)

    def _reset_calibration(self):
        self._coords_user = None
        self._coords_pass = None
        self._capturing = None
        self.launch_btn.setEnabled(True)
        self.launch_btn.setText("1. Avvia Riot Client per la calibrazione")
        self.user_btn.setEnabled(False)
        self.user_btn.setText("2. Clicca qui, poi clicca sul campo USERNAME nel Riot Client")
        self.pass_btn.setEnabled(False)
        self.pass_btn.setText("3. Clicca qui, poi clicca sul campo PASSWORD nel Riot Client")
        self.result_label.setText("")
        self.redo_btn.setVisible(False)
        self.err_label.setText("")

    def validatePage(self):
        _log("12. validatePage called")
        if not self._coords_user or not self._coords_pass:
            self.err_label.setText("Devi calibrare entrambi i campi prima di continuare.")
            return False
        _log("13. coords ok, closing riot via taskkill")
        def kill_riot():
            try:
                subprocess.run(["taskkill", "/F", "/IM", "RiotClientServices.exe"], 
                             capture_output=True)
                subprocess.run(["taskkill", "/F", "/IM", "LeagueClient.exe"], 
                             capture_output=True)
                subprocess.run(["taskkill", "/F", "/IM", "League of Legends.exe"], 
                             capture_output=True)
            except Exception:
                pass
        threading.Thread(target=kill_riot, daemon=True).start()
        _log("14. thread started, returning True")
        self.err_label.setText("")
        return True

    def get_coords(self):
        return self._coords_user, self._coords_pass

class WizardPageFirstAccount(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Aggiungi il tuo primo account")
        self.setSubTitle("Inserisci le credenziali del tuo account Riot.")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Nickname (nome visualizzato nell'app):"))
        self.nickname = QLineEdit()
        self.nickname.setPlaceholderText("es. Main Account")
        layout.addWidget(self.nickname)

        layout.addWidget(QLabel("Username Riot (login):"))
        self.login = QLineEdit()
        self.login.setPlaceholderText("Username Riot")
        layout.addWidget(self.login)

        layout.addWidget(QLabel("Password:"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password)

        self.show_cb = QCheckBox("Mostra password")
        self.show_cb.stateChanged.connect(
            lambda s: self.password.setEchoMode(QLineEdit.Normal if s else QLineEdit.Password)
        )
        layout.addWidget(self.show_cb)

        self.err_label = QLabel("")
        self.err_label.setStyleSheet("color: red;")
        layout.addWidget(self.err_label)

    def validatePage(self):
        if not self.nickname.text().strip():
            self.err_label.setText("Inserisci un nickname.")
            return False
        if not self.login.text().strip():
            self.err_label.setText("Inserisci l'username Riot.")
            return False
        if not self.password.text():
            self.err_label.setText("Inserisci la password.")
            return False
        self.err_label.setText("")
        return True

class WizardPageSummary(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Tutto pronto!")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "<b>Configurazione completata.</b><br><br>"
            "<b>Come usare l'app:</b><br>"
            "• Clicca sul nome di un account per avviare il gioco con quelle credenziali<br>"
            "• Usa <b>Aggiungi Account</b> per aggiungerne altri<br>"
            "• Il bottone <b>—</b> rimuove un account<br>"
            "• <b>Kill Riot</b> chiude tutti i processi Riot/League<br>"
            "• Da <b>Strumenti</b> puoi vedere le credenziali, esportare e importare account<br>"
            "• L'app si minimizza nella <b>tray</b> (vicino all'orologio)<br><br>"
            "Clicca <b>Finish</b> per aprire l'app."
        ))

class SetupWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Setup")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setMinimumSize(560, 500)

        self.page_welcome   = WizardPageWelcome()
        self.page_master    = WizardPageMasterPassword()
        self.page_riot      = WizardPageRiotPath()
        self.page_calib     = WizardPageCalibration()
        self.page_account   = WizardPageFirstAccount()
        self.page_summary   = WizardPageSummary()

        self.addPage(self.page_welcome)
        self.addPage(self.page_master)
        self.addPage(self.page_riot)
        self.addPage(self.page_calib)
        self.addPage(self.page_account)
        self.addPage(self.page_summary)

    def accept(self):
        cfg = load_config()
        cfg["riot_client_path"]      = self.field("riot_path")
        cfg["master_password_hash"]  = hash_master_password(self.field("master_password"))
        coords_user, coords_pass     = self.page_calib.get_coords()
        cfg["coords_username"]       = list(coords_user)
        cfg["coords_password"]       = list(coords_pass)
        cfg["setup_done"]            = True
        save_config(cfg)

        # Salva primo account
        accounts = decrypt_data()
        nick  = self.page_account.nickname.text().strip()
        login = self.page_account.login.text().strip()
        pw    = self.page_account.password.text()
        accounts[nick] = {"login": login, "password": pw}
        save_accounts(accounts)

        super().accept()

# ─── Dialog password dialog (aggiunta account) ────────────────────────────────

class PasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aggiungi Account")
        self.setMinimumWidth(320)
        self.setSizeGripEnabled(True)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Inserisci la password:"))
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.pw)
        cb = QCheckBox("Mostra password")
        cb.stateChanged.connect(lambda s: self.pw.setEchoMode(QLineEdit.Normal if s else QLineEdit.Password))
        layout.addWidget(cb)
        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

    def get_password(self):
        return self.pw.text()

# ─── Dialog recupero credenziali ─────────────────────────────────────────────

class RecoveryDialog(QDialog):
    def __init__(self, accounts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recupero credenziali")
        self.setMinimumSize(480, 300)
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        inner = QVBoxLayout(container)

        for nick, data in accounts.items():
            frame = QFrame()
            frame.setFrameShape(QFrame.StyledPanel)
            fl = QVBoxLayout(frame)
            fl.addWidget(QLabel(f"<b>{nick}</b>"))
            fl.addWidget(QLabel(f"Username: {data.get('login', '')}"))
            pw_label = QLabel(f"Password: {data.get('password', '')}")
            fl.addWidget(pw_label)
            inner.addWidget(frame)

        scroll.setWidget(container)
        layout.addWidget(scroll)
        btn = QPushButton("Chiudi")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)

# ─── Dialog export/import ─────────────────────────────────────────────────────

def _derive_key(password: str) -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    import base64
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32,
        salt=b"racm_export_salt", iterations=200_000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def _ask_export_password(parent, title, label):
    """Chiede una password (campo singolo) per decifrare un file .racm. Ritorna la stringa o None."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(360)
    dlg.setSizeGripEnabled(True)
    layout = QVBoxLayout(dlg)
    layout.setSpacing(8)
    layout.setContentsMargins(12, 12, 12, 12)
    lbl = QLabel(label)
    lbl.setWordWrap(True)
    layout.addWidget(lbl)
    pw = QLineEdit(); pw.setEchoMode(QLineEdit.Password)
    layout.addWidget(pw)
    err = QLabel(""); err.setStyleSheet("color: red;")
    layout.addWidget(err)
    btn = QPushButton("Conferma")
    result = [None]

    def confirm():
        if not pw.text():
            err.setText("Inserisci la password."); return
        result[0] = pw.text()
        dlg.accept()

    btn.clicked.connect(confirm)
    pw.returnPressed.connect(confirm)
    layout.addWidget(btn)
    dlg.exec()
    return result[0]

def export_accounts(accounts, cfg, parent):
    """Esporta gli account cifrati con la master password locale.
    Chi riceve il file deve conoscere questa password per importarlo."""
    pw = _ask_export_password(
        parent,
        "Conferma master password",
        "Inserisci la tua master password per esportare.\n"
        "Chi importa questo file dovrà conoscerla."
    )
    if pw is None:
        return
    if not verify_master_password(pw, cfg.get("master_password_hash", "")):
        QMessageBox.critical(parent, "Errore", "Master password errata.")
        return

    path, _ = QFileDialog.getSaveFileName(
        parent, "Esporta account", "accounts_backup.racm", "RACM Files (*.racm)"
    )
    if not path:
        return
    try:
        cipher    = Fernet(_derive_key(pw))
        encrypted = cipher.encrypt(json.dumps(accounts).encode())
        with open(path, "wb") as f:
            f.write(encrypted)
        QMessageBox.information(parent, "Esportazione completata", f"Account esportati in:\n{path}")
    except Exception as e:
        QMessageBox.critical(parent, "Errore", f"Esportazione fallita:\n{e}")

def import_accounts(existing_accounts, parent):
    """Importa account da un file .racm chiedendo la password di chi lo ha esportato."""
    path, _ = QFileDialog.getOpenFileName(
        parent, "Importa account", "", "RACM Files (*.racm)"
    )
    if not path:
        return existing_accounts

    pw = _ask_export_password(
        parent,
        "Password del file",
        "Inserisci la master password di chi ha esportato questo file:"
    )
    if pw is None:
        return existing_accounts

    try:
        cipher = Fernet(_derive_key(pw))
        with open(path, "rb") as f:
            data = json.loads(cipher.decrypt(f.read()).decode())
        merged = {**existing_accounts, **data}
        save_accounts(merged)
        QMessageBox.information(
            parent, "Importazione completata",
            f"Importati {len(data)} account. Totale: {len(merged)}."
        )
        return merged
    except Exception:
        QMessageBox.critical(parent, "Errore", "File non valido o password errata.")
        return existing_accounts

def ask_master_password(cfg, parent, action_label="continuare"):
    """Mostra un dialog per chiedere la master password. Ritorna True se corretta."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Master Password richiesta")
    dlg.setMinimumWidth(340)
    dlg.setSizeGripEnabled(True)
    layout = QVBoxLayout(dlg)
    layout.setSpacing(8)
    layout.setContentsMargins(12, 12, 12, 12)
    lbl = QLabel(f"Inserisci la master password per {action_label}:")
    lbl.setWordWrap(True)
    layout.addWidget(lbl)
    pw_edit = QLineEdit()
    pw_edit.setEchoMode(QLineEdit.Password)
    layout.addWidget(pw_edit)
    err = QLabel("")
    err.setStyleSheet("color: red;")
    layout.addWidget(err)
    btn = QPushButton("Conferma")

    result = [False]

    def confirm():
        if verify_master_password(pw_edit.text(), cfg.get("master_password_hash", "")):
            result[0] = True
            dlg.accept()
        else:
            err.setText("Password errata.")

    btn.clicked.connect(confirm)
    pw_edit.returnPressed.connect(confirm)
    layout.addWidget(btn)
    dlg.exec()
    return result[0]

# ─── Finestra principale ──────────────────────────────────────────────────────

class AccountManager(QWidget):
    def __init__(self):
        super().__init__()
        self.config   = load_config()
        self.accounts = decrypt_data()

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(APP_ICON))
        self.setGeometry(100, 100, 420, 480)
        self.setMinimumWidth(380)

        root = QVBoxLayout(self)

        # Area scrollabile per gli account
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.account_container = QWidget()
        self.account_layout    = QVBoxLayout(self.account_container)
        self.account_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.account_container)
        root.addWidget(scroll)

        # Pulsanti in basso
        bottom = QVBoxLayout()

        self.game_selector = QComboBox()
        self.game_selector.addItems(["League of Legends", "Valorant"])
        bottom.addWidget(self.game_selector)

        # Spinbox per il delay di login
        delay_layout = QHBoxLayout()
        delay_label = QLabel("Delay login (sec):")
        delay_layout.addWidget(delay_label)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(1.0, 15.0)
        self.delay_spin.setSingleStep(0.5)
        self.delay_spin.setDecimals(1)
        self.delay_spin.setValue(self.config.get("login_delay", 3.0))
        self.delay_spin.setToolTip("Aumenta se le credenziali vengono inserite prima che il client sia pronto")
        self.delay_spin.valueChanged.connect(self._save_delay)
        delay_layout.addWidget(self.delay_spin)
        bottom.addLayout(delay_layout)

        self.add_btn = QPushButton("➕  Aggiungi Account")
        self.add_btn.clicked.connect(self.add_account)
        bottom.addWidget(self.add_btn)

        tools_layout = QHBoxLayout()

        self.recovery_btn = QPushButton("🔑  Recupera credenziali")
        self.recovery_btn.clicked.connect(self.show_recovery)
        tools_layout.addWidget(self.recovery_btn)

        self.export_btn = QPushButton("📤  Esporta")
        self.export_btn.clicked.connect(self.export)
        tools_layout.addWidget(self.export_btn)

        self.import_btn = QPushButton("📥  Importa")
        self.import_btn.clicked.connect(self.import_accs)
        tools_layout.addWidget(self.import_btn)

        bottom.addLayout(tools_layout)

        self.kill_btn = QPushButton("☠  Kill Riot")
        self.kill_btn.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.kill_btn.clicked.connect(close_riot_processes)
        bottom.addWidget(self.kill_btn)

        root.addLayout(bottom)

        self._build_account_list()
        self._setup_tray()
        self._check_updates()

    # ── UI account list ───────────────────────────────────────────────────────

    def _build_account_list(self):
        # Pulisce
        while self.account_layout.count():
            item = self.account_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        for username in self.accounts:
            row = QHBoxLayout()
            btn = QPushButton(username)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(partial(self.start_game, username))
            row.addWidget(btn)

            rm = QPushButton("—")
            rm.setFixedSize(32, 32)
            rm.setStyleSheet("color: #9b59b6; background: none; border: none; font-weight: bold; font-size: 20px;")
            rm.clicked.connect(partial(self.remove_account, username))
            row.addWidget(rm)

            wrapper = QWidget()
            wrapper.setLayout(row)
            self.account_layout.addWidget(wrapper)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── Tray ─────────────────────────────────────────────────────────────────

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(QIcon(APP_ICON), self)
        menu = QMenu()
        menu.addAction("Apri", self._restore)
        menu.addAction("Kill Riot", close_riot_processes)
        menu.addSeparator()
        menu.addAction("Esci", QApplication.quit)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(
            lambda r: self._restore() if r == QSystemTrayIcon.DoubleClick else None
        )
        self.tray.show()

    def _restore(self):
        self.showNormal()
        self.activateWindow()

    def _save_delay(self, value):
        cfg = load_config()
        cfg["login_delay"] = value
        save_config(cfg)
        self.config = cfg

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage(APP_NAME, "L'app è ancora attiva nella tray.", QSystemTrayIcon.Information, 2000)

    # ── Aggiornamenti ─────────────────────────────────────────────────────────

    def _check_updates(self):
        self._update_checker = UpdateChecker()
        self._update_checker.update_available.connect(
            lambda v, u: show_update_dialog(self, v, u)
        )
        threading.Thread(target=self._update_checker.check, daemon=True).start()

    # ── Avvio gioco ───────────────────────────────────────────────────────────

    def start_game(self, username):
        self.hide()  # va nella tray
        self.config = load_config()
        select_account(username, self.accounts, self.game_selector.currentText(), self.config)

    # ── Gestione account ──────────────────────────────────────────────────────

    def add_account(self):
        username, ok = QInputDialog.getText(self, "Aggiungi Account", "Nickname (nome visualizzato):")
        if not ok or not username.strip():
            return
        login, ok = QInputDialog.getText(self, "Aggiungi Account", "Username Riot (login):")
        if not ok or not login.strip():
            return
        dlg = PasswordDialog(self)
        if dlg.exec() != QDialog.Accepted or not dlg.get_password():
            return
        self.accounts[username.strip()] = {"login": login.strip(), "password": dlg.get_password()}
        save_accounts(self.accounts)
        self._build_account_list()

    def remove_account(self, username):
        if QMessageBox.question(
            self, "Elimina account", f"Eliminare '{username}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) == QMessageBox.Yes:
            self.accounts.pop(username, None)
            save_accounts(self.accounts)
            self._build_account_list()

    # ── Recupero credenziali ──────────────────────────────────────────────────

    def show_recovery(self):
        self.config = load_config()
        if not ask_master_password(self.config, self, "vedere le credenziali"):
            return
        RecoveryDialog(self.accounts, self).exec()

    # ── Export / Import ───────────────────────────────────────────────────────

    def export(self):
        self.config = load_config()
        export_accounts(self.accounts, self.config, self)

    def import_accs(self):
        self.accounts = import_accounts(self.accounts, self)
        self._build_account_list()

# ─── Entry point ──────────────────────────────────────────────────────────────

def _global_exception_handler(exc_type, exc_value, exc_tb):
    import traceback
    log_path = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "crash_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))

def _fix_ssl():
    if hasattr(sys, "_MEIPASS"):
        cert = os.path.join(sys._MEIPASS, "certifi", "cacert.pem")
        if os.path.exists(cert):
            os.environ["SSL_CERT_FILE"] = cert
            os.environ["REQUESTS_CA_BUNDLE"] = cert

def _log(msg):
    """Scrive un messaggio di debug su file in AppData."""
    try:
        log_path = os.path.join(os.environ.get("APPDATA", "."), "RiotAccountsManager", "debug_log.txt")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

if __name__ == "__main__":
    sys.excepthook = _global_exception_handler
    _fix_ssl()
    generate_key()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon("info/ico/256x256.ico"))

    cfg = load_config()
    if not cfg.get("setup_done"):
        wizard = SetupWizard()
        if wizard.exec() != QWizard.Accepted:
            sys.exit(0)

    window = AccountManager()
    window.show()
    sys.exit(app.exec())
