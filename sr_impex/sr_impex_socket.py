import bpy
import socket
import threading
import queue
import json
import time

# --- Konfiguration der Erweiterung ---
HOST = "127.0.0.1"
# Fester Port für den GUI-Server, der auf Nachrichten von Blender wartet
GUI_SERVER_PORT = 65433
# Fester Port für den Blender-Server, der auf Nachrichten von der GUI wartet
BLENDER_SERVER_PORT = 65432

# Eine Thread-sichere Warteschlange, um Nachrichten an den Hauptthread von Blender zu übergeben
MESSAGE_QUEUE = queue.Queue()
CLIENT_CONNECTION = None
SERVER_SOCKET = None
STOP_SERVER_EVENT = threading.Event()  # Ereignis, um den Server-Thread zu stoppen
RUNNING_OPERATOR_INSTANCE = (
    None  # Globale Variable zur Verfolgung der laufenden Operator-Instanz
)


class SocketClient:
    """Ein einfacher Client, um eine einzelne Nachricht an einen Server zu senden."""

    def __init__(self, host=HOST, port=GUI_SERVER_PORT):
        self.host = host
        self.port = port
        self.socket = None

    def connect(self):
        """Stellt eine Verbindung zum GUI-Server her."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            return True
        except ConnectionRefusedError:
            print(
                f"SocketClient: Verbindung verweigert. Läuft die GUI auf Port {self.port}?"
            )
            self.socket = None
            return False

    def send_message(self, message: dict):
        """
        Sendet eine Nachricht an den verbundenen GUI-Server.
        """
        if self.socket:
            json_message = json.dumps(message)
            self.socket.sendall(json_message.encode("utf-8"))
            print(f"SocketClient (Client): Gesendete Nachricht: {json_message}")
        else:
            print(
                "SocketClient (Client): Nicht verbunden. Nachricht wurde nicht gesendet."
            )

    def disconnect(self):
        """Schließt die Verbindung."""
        if self.socket:
            self.socket.close()
            self.socket = None
            print("SocketClient (Client): Verbindung getrennt.")


def send_path_to_gui(file_path: str):
    """
    Erstellt einen Client, sendet eine Dateipfad-Nachricht an die GUI und trennt die Verbindung.
    """
    client = SocketClient()
    if client.connect():
        message = {"action": "load_file", "path": file_path}
        client.send_message(message)
        client.disconnect()


# --- Blender-sichere Befehlsausführung ---
def process_queued_messages():
    """
    Diese Funktion wird im Hauptthread von Blender ausgeführt und verarbeitet
    Nachrichten aus der Warteschlange.
    """
    while not MESSAGE_QUEUE.empty():
        try:
            message = MESSAGE_QUEUE.get_nowait()
            print(f"Blender hat Befehl von GUI erhalten: {message}")

            # Markiert die Aufgabe als erledigt
            MESSAGE_QUEUE.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Fehler bei der Verarbeitung der Nachricht: {e}")


# --- Socket-Server-Thread ---
def socket_server_thread():
    """
    Dieser Thread führt den Socket-Server aus und lauscht auf Client-Verbindungen (von der GUI).
    """
    global CLIENT_CONNECTION, SERVER_SOCKET, STOP_SERVER_EVENT
    print(f"Blender-Server startet auf {HOST}:{BLENDER_SERVER_PORT}")
    try:
        SERVER_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        SERVER_SOCKET.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        SERVER_SOCKET.bind((HOST, BLENDER_SERVER_PORT))
        SERVER_SOCKET.listen(1)
        SERVER_SOCKET.settimeout(1.0)
        while not STOP_SERVER_EVENT.is_set():
            try:
                conn, addr = SERVER_SOCKET.accept()
                print(f"Blender-Server: Client verbunden von {addr}")
                CLIENT_CONNECTION = conn
                while not STOP_SERVER_EVENT.is_set():
                    data = conn.recv(1024)
                    if not data:
                        print(f"Client {addr} getrennt.")
                        break
                    try:
                        message_dict = json.loads(data.decode("utf-8"))
                        MESSAGE_QUEUE.put(message_dict)
                    except json.JSONDecodeError:
                        print(
                            f"Blender-Server: Fehlerhafte JSON-Nachricht erhalten: {data}"
                        )
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Ein Fehler ist in der Blender-Server-Schleife aufgetreten: {e}")
            finally:
                if CLIENT_CONNECTION:
                    CLIENT_CONNECTION.close()
                    CLIENT_CONNECTION = None
    except Exception as e:
        print(f"Fehler beim Binden an den Blender-Socket: {e}")
        STOP_SERVER_EVENT.set()
    finally:
        if SERVER_SOCKET:
            SERVER_SOCKET.close()
        print("Blender-Server-Thread gestoppt.")


# --- Blender-Operatoren ---
class StartSocketSyncOperator(bpy.types.Operator):
    bl_idname = "wm.start_socket_sync_operator"
    bl_label = "Start Socket Sync Operator"

    _timer = None
    _server_thread = None

    def modal(self, context, event):
        if event.type == "TIMER":
            process_queued_messages()
            if STOP_SERVER_EVENT.is_set():
                print("Stoppt Modal-Timer.")
                self.cancel(context)
                return {"CANCELLED"}
        return {"PASS_THROUGH"}

    def execute(self, context):
        global RUNNING_OPERATOR_INSTANCE
        if RUNNING_OPERATOR_INSTANCE is not None:
            self.report({"INFO"}, "Die Socket-Synchronisation läuft bereits.")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Blender-Server startet auf Port {BLENDER_SERVER_PORT}")
        RUNNING_OPERATOR_INSTANCE = self
        STOP_SERVER_EVENT.clear()
        self._server_thread = threading.Thread(target=socket_server_thread, daemon=True)
        self._server_thread.start()

        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)

        return {"RUNNING_MODAL"}

    def cancel(self, context):
        try:
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None
        except (ValueError, KeyError):
            pass

        STOP_SERVER_EVENT.set()
        global RUNNING_OPERATOR_INSTANCE
        RUNNING_OPERATOR_INSTANCE = None

        return {"CANCELLED"}


class StopSocketSyncOperator(bpy.types.Operator):
    bl_idname = "wm.stop_socket_sync_operator"
    bl_label = "Stop Socket Sync Operator"

    def execute(self, context):
        global RUNNING_OPERATOR_INSTANCE
        if RUNNING_OPERATOR_INSTANCE is not None:
            # Setzt einfach das Stopp-Ereignis. Der laufende Operator-Thread
            # kümmert sich um die eigene Bereinigung.
            STOP_SERVER_EVENT.set()
            self.report({"INFO"}, "Signal zum Stoppen des Servers gesendet.")
        else:
            self.report({"INFO"}, "Der Server läuft nicht.")
        return {"FINISHED"}


# --- Blender-UI-Panel zum Aufrufen der Operatoren ---
class DRS_PT_SocketPanel(bpy.types.Panel):
    bl_label = "DRS Tools"  # Changed label to be more general
    bl_idname = "DRS_PT_SocketPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DRS"

    def draw(self, context):
        layout = self.layout

        # --- Existing Socket Sync Section ---
        box = layout.box()
        row = box.row()
        row.label(text="Socket Synchronization", icon="NETWORK_DRIVE")

        if RUNNING_OPERATOR_INSTANCE is None:
            row = box.row()
            row.operator("wm.start_socket_sync_operator", text="Start Server")
        else:
            row = box.row()
            row.label(text=f"Server running on Port {BLENDER_SERVER_PORT}", icon="INFO")
            row = box.row()
            row.operator("wm.stop_socket_sync_operator", text="Stop Server")

        row = box.row()
        row.label(text=f"GUI Connection on Port {GUI_SERVER_PORT}")

        # --- NEW SECTION FOR DEBUGGING ---
        layout.separator()

        box = layout.box()
        row = box.row()
        row.label(text="Debugging Tools", icon="TOOL_SETTINGS")

        row = box.row()
        # This is the new button
        row.operator("drs.debug_obb_tree", text="Generate OBBTree")
