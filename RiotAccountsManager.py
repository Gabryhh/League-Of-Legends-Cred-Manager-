import json
import os
import subprocess
import time
import ctypes
import pyautogui
import pyperclip
import psutil
import pygetwindow as gw
from PySide6.QtGui import QIcon
from cryptography.fernet import Fernet
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QInputDialog, QMessageBox, QComboBox, QLineEdit, QCheckBox, QDialog, QLabel
)
from functools import partial

# File di configurazione
KEY_FILE = "key.key"
DATA_FILE = "accounts.enc"

# Genera una chiave di crittografia
def generate_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as key_file:
            key_file.write(key)

# Carica la chiave salvata
def load_key():
    with open(KEY_FILE, "rb") as key_file:
        return key_file.read()

# Cifra i dati prima di salvarli
def encrypt_data(data):
    key = load_key()
    cipher = Fernet(key)
    return cipher.encrypt(json.dumps(data).encode())

# Decifra i dati salvati
def decrypt_data():
    if not os.path.exists(DATA_FILE):
        return {}
    
    key = load_key()
    cipher = Fernet(key)
    with open(DATA_FILE, "rb") as file:
        decrypted_data = cipher.decrypt(file.read())
        return json.loads(decrypted_data.decode())

# Salva gli account cifrati nel file
def save_accounts(accounts):
    encrypted_data = encrypt_data(accounts)
    with open(DATA_FILE, "wb") as file:
        file.write(encrypted_data)

# Chiude tutti i processi di Riot Games e League of Legends
def close_riot_processes():
    for process in psutil.process_iter(attrs=['pid', 'name']):
        if any(riot_proc in process.info['name'].lower() for riot_proc in ["riot", "league"]):
            try:
                psutil.Process(process.info['pid']).terminate()
            except psutil.NoSuchProcess:
                pass
    time.sleep(3)

# Ritorna il rettangolo del monitor (left, top, right, bottom) che contiene il punto (x, y)
def get_monitor_rect_at(x, y):
    user32 = ctypes.windll.user32
    MONITOR_DEFAULTTONEAREST = 0x00000002
    hmon = user32.MonitorFromPoint(ctypes.wintypes.POINT(x, y), MONITOR_DEFAULTTONEAREST)

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", ctypes.wintypes.RECT),
            ("rcWork",    ctypes.wintypes.RECT),
            ("dwFlags",   ctypes.c_ulong),
        ]

    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(hmon, ctypes.byref(info))
    r = info.rcMonitor
    return (r.left, r.top, r.right, r.bottom)


# Minimizza tutte le finestre visibili sullo stesso monitor della finestra target
def minimize_windows_on_same_monitor(target_window):
    try:
        cx = target_window.left + target_window.width  // 2
        cy = target_window.top  + target_window.height // 2
        mon = get_monitor_rect_at(cx, cy)
    except Exception:
        return

    for win in gw.getAllWindows():
        if win == target_window:
            continue
        if not win.visible or win.isMinimized:
            continue
        # Salta finestre senza titolo (es. tray, overlay) e l'Account Manager stesso
        if not win.title.strip():
            continue
        if "Riot Accounts Manager" in win.title:
            continue
        try:
            wcx = win.left + win.width  // 2
            wcy = win.top  + win.height // 2
            if mon[0] <= wcx < mon[2] and mon[1] <= wcy < mon[3]:
                win.minimize()
        except Exception:
            pass


# Seleziona un account e avvia il Riot Client
def select_account(username, accounts, game):
    user = accounts.get(username)
    if not user:
        return
    
    close_riot_processes()

    game_mapping = {
        "League of Legends": "league_of_legends",
        "Valorant": "valorant"
    }
    
    subprocess.Popen([ 
        "C:\\Riot Games\\Riot Client\\RiotClientServices.exe",
        f"--launch-product={game_mapping.get(game, 'league_of_legends')}",
        "--launch-patchline=live"
    ])

    # Attende che la finestra del Riot Client sia visibile e non minimizzata
    timeout = 60
    poll_interval = 0.5
    elapsed = 0
    riot_window = None
    while elapsed < timeout:
        windows = gw.getWindowsWithTitle("Riot Client")
        if windows:
            w = windows[0]
            if w.visible and not w.isMinimized:
                riot_window = w
                break
        time.sleep(poll_interval)
        elapsed += poll_interval

    if riot_window is None:
        return  # finestra non trovata entro il timeout, annulla

    # Porta il Riot Client in primo piano e aspetta che la UI sia pronta
    riot_window.activate()
    time.sleep(3.0)

    # Campo username
    pyautogui.click(420, 506)
    time.sleep(0.5)
    pyperclip.copy(user["login"])
    pyautogui.hotkey("ctrl", "v")

    # Campo password
    pyautogui.click(421, 585)
    time.sleep(0.5)
    pyperclip.copy(user["password"])
    pyautogui.hotkey("ctrl", "v")

    pyautogui.press("enter")

# Classe per il dialog personalizzato di inserimento password
class PasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aggiungi Account")
        self.setFixedSize(300, 150)

        layout = QVBoxLayout()

        self.label = QLabel("Inserisci la password:")
        layout.addWidget(self.label)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_input)

        self.show_password_checkbox = QCheckBox("Mostra password")
        self.show_password_checkbox.stateChanged.connect(self.toggle_password_visibility)
        layout.addWidget(self.show_password_checkbox)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def toggle_password_visibility(self):
        if self.show_password_checkbox.isChecked():
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)

    def get_password(self):
        return self.password_input.text()

# Classe principale dell'app
class AccountManager(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Riot Accounts Manager by Gabry©")
        #self.setWindowIcon(QIcon("info/ico/ico2.ico"))

        self.setGeometry(100, 100, 400, 400)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Layout per gli account
        self.account_layout = QVBoxLayout()
        self.layout.addStretch()
        self.layout.addLayout(self.account_layout)

        # Layout per i pulsanti in basso
        self.bottom_layout = QVBoxLayout()
        self.layout.addStretch()
        self.layout.addLayout(self.bottom_layout)

        self.update_ui()

    def update_ui(self):
        while self.account_layout.count():
            item = self.account_layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    sub_item = item.layout().takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()
            if item.widget():
                item.widget().deleteLater()

        while self.bottom_layout.count():
            item = self.bottom_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.accounts = decrypt_data()
        
        for username in self.accounts.keys():
            account_layout = QHBoxLayout()
            
            account_btn = QPushButton(username)
            account_btn.clicked.connect(partial(self.start_game, username))
            account_layout.addWidget(account_btn)

            remove_btn = QPushButton("-")
            remove_btn.setFixedSize(30, 30)
            remove_btn.setStyleSheet("color: purple; background: none; border: none; font-weight: bold; font-size: 25px; ")
            remove_btn.clicked.connect(partial(self.remove_account, username))
            account_layout.addWidget(remove_btn)
            
            self.account_layout.addLayout(account_layout)

        self.add_account_button = QPushButton("Aggiungi Account")
        self.add_account_button.clicked.connect(self.add_account)
        self.bottom_layout.addWidget(self.add_account_button)

        self.game_selector = QComboBox()
        self.game_selector.addItems(["League of Legends", "Valorant"])
        self.bottom_layout.addWidget(self.game_selector)

        self.kill_riot_button = QPushButton("Kill Riot")
        self.kill_riot_button.setStyleSheet("background-color: red; color: white;")
        self.kill_riot_button.clicked.connect(close_riot_processes)
        self.bottom_layout.addWidget(self.kill_riot_button)

    def start_game(self, username):
        self.showMinimized()  # minimizza subito l'Account Manager
        time.sleep(0.5)

        # Minimizza tutte le finestre visibili sul monitor primario
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

        selected_game = self.game_selector.currentText()
        select_account(username, self.accounts, selected_game)

    def add_account(self):
        username, ok = QInputDialog.getText(self, "Aggiungi Account", "Inserisci il nickname:")
        if not ok or not username:
            return
        
        login, ok = QInputDialog.getText(self, "Aggiungi Account", "Inserisci il nome utente:")
        if not ok or not login:
            return
        
        password_dialog = PasswordDialog(self)
        if password_dialog.exec() == QDialog.Accepted:
            password = password_dialog.get_password()
            if not password:
                return
            
            self.accounts[username] = {"login": login, "password": password}
            save_accounts(self.accounts)
            self.update_ui()

    def remove_account(self, username):
        confirm = QMessageBox.question(
            self, "Conferma Eliminazione", f"Eliminare l'account '{username}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            if username in self.accounts:
                del self.accounts[username]
                save_accounts(self.accounts)
                self.update_ui()

# Avvio dell'applicazione
if __name__ == "__main__":
    generate_key()
    app = QApplication([])
    app.setWindowIcon(QIcon("info/ico/256x256.ico"))
    window = AccountManager()
    window.show()
    app.exec()
