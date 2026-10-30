import os
import re
import socket
import subprocess
import sys
import threading
import time
import random
import chess

class MotorUciSimulado:
    """
    Simulador interno UCI para garantizar autonomía absoluta al copiar y pegar.
    Emula el comportamiento de un ejecutable externo respondiendo comandos UCI de forma asíncrona.
    """
    def __init__(self):
        self.board = chess.Board()

    def enviar_comando(self, comando):
        comando = comando.strip()
        if comando == "uci":
            return "id name MotorInternoAutonomo\nid author IA\nuciok"
        elif comando == "isready":
            return "readyok"
        elif comando.startswith("position startpos moves"):
            self.board.reset()
            try:
                parts = comando.split("moves ")
                if len(parts) > 1:
                    moves = parts[1].split()
                    for m in moves:
                        self.board.push(chess.Move.from_uci(m))
            except Exception:
                pass
            return None
        elif comando == "position startpos":
            self.board.reset()
            return None
        elif comando.startswith("go"):
            if self.board.is_game_over():
                return None
            legal_moves = list(self.board.legal_moves)
            if legal_moves:
                chosen_move = random.choice(legal_moves)
                return f"bestmove {chosen_move.uci()}"
            return None
        return None


class FicsUciAdapter:
    def __init__(self, mode="SIMULADO", engine_path="", tcp_ip="127.0.0.1", tcp_port=6110, engine_args=None):
        self.mode = mode.upper()
        self.engine_path = engine_path
        self.tcp_ip = tcp_ip
        self.tcp_port = tcp_port
        self.engine_args = engine_args if engine_args else {}

        self.fics_host = "freechess.org"
        self.fics_port = 5000
        self.username = "guest"
        self.password = ""

        self.fics_socket = None
        self.engine_process = None
        self.engine_socket = None
        self.running = True
        
        self.board = chess.Board()
        self.my_color = None  
        self.in_game = False

        self.simulador = MotorUciSimulado() if self.mode == "SIMULADO" else None

        self.challenge_regex = re.compile(r"Challenge:\s+(\S+)\s+\((\d+)\)\s+(\S+)\s+\((\d+)\)\s+unrated", re.IGNORECASE)
        self.accept_command_regex = re.compile(r"Use\s+'(accept\s+\d+|play\s+\d+)'", re.IGNORECASE)

    def log(self, tag, message):
        print(f"[{time.strftime('%H:%M:%S')}] [{tag}] {message}")

    def start_engine(self):
        if self.mode == "SIMULADO":
            self.log("MOTOR-SIM", "Inicializando motor UCI simulado interno...")
            return

        if self.mode == "TCP":
            self.log("MOTOR-TCP", f"Conectando al motor UCI en {self.tcp_ip}:{self.tcp_port}...")
            try:
                self.engine_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.engine_socket.connect((self.tcp_ip, self.tcp_port))
                self.log("MOTOR-TCP", "¡Conexión de red establecida con el motor!")
            except Exception as e:
                self.log("ERROR-CRÍTICO", f"No se pudo conectar al motor UCI por TCP: {e}")
                sys.exit(1)
            threading.Thread(target=self.listen_engine_tcp, daemon=True).start()
        
        elif self.mode == "PIPE":
            cmd_list = [self.engine_path]
            for key, val in self.engine_args.items():
                cmd_list.append(f"--{key}")
                cmd_list.append(str(val))
            
            self.log("MOTOR-LOCAL", f"Iniciando subproceso del motor: {' '.join(cmd_list)}")
            try:
                self.engine_process = subprocess.Popen(
                    cmd_list,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
            except Exception as e:
                self.log("ERROR-CRÍTICO", f"No se pudo lanzar el ejecutable local del motor: {e}")
                sys.exit(1)
            threading.Thread(target=self.listen_engine_local, daemon=True).start()

        self.send_to_engine("uci")
        self.send_to_engine("isready")

    def send_to_engine(self, command):
        if self.mode == "SIMULADO":
            respuesta = self.simulador.enviar_comando(command)
            if respuesta:
                threading.Thread(target=lambda: (time.sleep(0.5), self.handle_engine_line(respuesta)), daemon=True).start()
            return

        if not command.endswith("\n"):
            command += "\n"
        
        if self.mode == "TCP" and self.engine_socket:
            try:
                self.engine_socket.sendall(command.encode("utf-8"))
            except Exception as e:
                self.log("ERROR", f"Error de escritura TCP hacia el motor: {e}")
        elif self.mode == "PIPE" and self.engine_process and self.engine_process.stdin:
            try:
                self.engine_process.stdin.write(command)
                self.engine_process.stdin.flush()
            except Exception as e:
                self.log("ERROR", f"Error de escritura Pipe hacia el motor: {e}")

    def listen_engine_local(self):
        for line in iter(self.engine_process.stdout.readline, ""):
            line = line.strip()
            if line:
                self.handle_engine_line(line)

    def listen_engine_tcp(self):
        buffer = ""
        while self.running:
            try:
                data = self.engine_socket.recv(4096).decode("utf-8", errors="ignore")
                if not data:
                    self.log("MOTOR-TCP", "El motor cerró la conexión de red.")
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self.handle_engine_line(line)
            except:
                break

    def handle_engine_line(self, line):
        if line.startswith("bestmove"):
            parts = line.split()
            if len(parts) >= 2:
                best_move_uci = parts[1]
                self.log("MOTOR", f"Jugada recibida del motor (UCI): {best_move_uci}")

                if not self.in_game:
                    self.log("SISTEMA", "Jugada descartada: No hay partida activa en FICS.")
                    return

                try:
                    move = chess.Move.from_uci(best_move_uci)
                    fics_notation = self.board.san(move)
                    self.board.push(move)
                    self.log("ADAPTADOR", f"Traducción completada: {best_move_uci} -> {fics_notation}")
                    self.send_to_fics(fics_notation)
                except Exception as e:
                    self.log("ERROR", f"Error crítico al traducir la jugada del motor: {e}")

    def connect_fics(self):
        self.log("FICS", f"Conectando a {self.fics_host}:{self.fics_port}...")
        try:
            self.fics_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.fics_socket.connect((self.fics_host, self.fics_port))
        except Exception as e:
            self.log("ERROR-CRÍTICO", f"No se pudo conectar al servidor de red FICS: {e}")
            sys.exit(1)

        threading.Thread(target=self.listen_fics, daemon=True).start()

        time.sleep(1.5)
        self.log("FICS", f"Enviando credencial de acceso: {self.username}")
        self.send_to_fics(self.username)
        time.sleep(1.5)
        self.send_to_fics("")  
        time.sleep(1.5)

        self.log("FICS", "Inicializando variables de protocolo remoto...")
        self.send_to_fics("set style 12")  
        self.send_to_fics("set pin 1")     
        self.send_to_fics("set open 1")    
        self.log("SISTEMA", f"Adaptador corriendo en modo [{self.mode}]. Esperando retos amistosos en FICS...")

    def send_to_fics(self, command):
        if self.fics_socket:
            try:
                self.fics_socket.sendall(f"{command}\n".encode("utf-8"))
            except Exception as e:
                self.log("ERROR", f"Error de escritura en el socket FICS: {e}")

    def listen_fics(self):
        buffer = ""
        while self.running:
            try:
                data = self.fics_socket.recv(4096).decode("utf-8", errors="ignore")
                if not data:
                    self.log("FICS", "El servidor remoto FICS cerró la sesión.")
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self.parse_fics_line(line)
            except:
                break

    def parse_fics_line(self, line):
        if line.startswith("<12>"):
            fields = line.split()
            if len(fields) < 27:
                return

            whose_turn = fields[9]          
            last_move_fics = fields[24]     
            game_status = int(fields[26])   

            if game_status == 0:
                if self.in_game:
                    self.log("SISTEMA", "La partida ha concluido. Reseteando el estado interno.")
                    self.board.reset()
                    self.my_color = None
                    self.in_game = False
                return

            if not self.in_game:
                white_player = fields[17]
                if self.username.lower() in white_player.lower():
                    self.my_color = "W"
                else:
                    self.my_color = "B"
                self.in_game = True
                self.board.reset()
                self.log("SISTEMA", f"¡Partida detectada en FICS! Color asignado al motor: {self.my_color}")

            if whose_turn == self.my_color:
                if last_move_fics.lower() != "none":
                    try:
                        clean_fics_move = last_move_fics.replace("-", "")
                        parsed_move = self.board.parse_san(clean_fics_move)
                        if len(self.board.move_stack) == 0 or self.board.peek() != parsed_move:
                            self.board.push(parsed_move)
                    except ValueError:
                        try:
                            parsed_move = self.board.parse_uci(clean_fics_move)
                            self.board.push(parsed_move)
                        except Exception as e:
                            self.log("ERROR", f"Imposible parsear la jugada entrante de FICS '{last_move_fics}': {e}")
                            return

                self.log("FICS", "Turno de tu motor. Construyendo historial de comandos UCI...")
                
                moves_list = [m.uci() for m in self.board.move_stack]
                if moves_list:
                    position_command = f"position startpos moves {' '.join(moves_list)}"
                else:
                    position_command = "position startpos"

                self.send_to_engine(position_command)
                self.send_to_engine("go movetime 2000")  
            return

        if not self.in_game and ("challenge" in line.lower() or "unrated" in line.lower() or "use 'accept'" in line.lower()):
            match_cmd = self.accept_command_regex.search(line)
            if match_cmd:
                accept_command = match_cmd.group(1)
                self.log("SISTEMA", f"¡Reto detectado! Enviando comando de aceptación: '{accept_command}'")
                self.send_to_fics(accept_command)
                return
            if self.challenge_regex.search(line):
                self.log("SISTEMA", "Reto detectado por patrón. Enviando comando 'accept'...")
                self.send_to_fics("accept")

    def stop(self):
        self.log("SISTEMA", "Apagando el adaptador de forma segura...")
        self.running = False
        if self.engine_socket:
            try: self.engine_socket.close()
            except: pass
        if self.engine_process:
            try: self.engine_process.terminate()
            except: pass
        if self.fics_socket:
            try: self.fics_socket.close()
            except: pass
        self.log("SISTEMA", "Recursos liberados. Adaptador apagado con éxito.")


if __name__ == "__main__":
    MODO_ACTIVO = "SIMULADO"  

    RUTA_MOTOR_LOCAL = "./mi_motor_uci"  
    ARGUMENTOS_MOTOR_LOCAL = {
        "hash": 256,
        "threads": 2
    }

    IP_MOTOR_REMOTO = "127.0.0.1"
    PUERTO_MOTOR_REMOTO = 6110

    adapter = FicsUciAdapter(
        mode=MODO_ACTIVO,
        engine_path=RUTA_MOTOR_LOCAL, 
        tcp_ip=IP_MOTOR_REMOTO, 
        tcp_port=PUERTO_MOTOR_REMOTO, 
        engine_args=ARGUMENTOS_MOTOR_LOCAL
    )
    
    adapter.start_engine()
    adapter.connect_fics()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        adapter.stop()
