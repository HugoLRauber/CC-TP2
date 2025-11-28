import subprocess
import sys
import time
import os

def lancar_frota():
    print("--- CENTRAL DE LANÇAMENTO DA FROTA ---")
    print("A preparar sistemas...")

    # Nomes dos Rovers que queremos criar
    lista_rovers = [
        "Rover-Alpha",
        "Rover-Beta",
        "Rover-Gamma"
    ]

    python_exe = sys.executable

    for nome in lista_rovers:
        print(f">>> A lançar {nome}...")

        # Comando para Windows (abre nova janela CMD)
        if os.name == 'nt':
            cmd = f'start "{nome}" cmd /k "{python_exe} rover.py {nome}"'
        # Comando para Linux (tenta xterm ou gnome-terminal)
        else:
            cmd = f'xterm -T "{nome}" -e "{python_exe} rover.py {nome}" &'

        subprocess.Popen(cmd, shell=True)
        time.sleep(0.5)

    print("\n 3 Rovers lançados!")
    print("Vá a cada janela e pressione ENTER para pedir missões.")

if __name__ == "__main__":
    lancar_frota()