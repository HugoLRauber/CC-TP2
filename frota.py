import subprocess
import sys
import time

def lancar_frota():
    print("--- LANÇAMENTO DA FROTA DE ROVERS ---")

    # 1. Defina aqui os seus rovers
    lista_rovers = [
        "Rover-Alpha",
        "Rover-Beta",
        "Rover-Gamma",
        "Rover-Delta"
    ]

    python_exe = sys.executable

    # 2. Loop para lançar cada um
    for nome_rover in lista_rovers:
        print(f">>> A ativar sistemas do {nome_rover}...")

        # Comando para abrir nova janela a correr o rover.py com o nome específico
        # Windows: start "Titulo" cmd /k python rover.py "Nome"
        comando = f'start "{nome_rover}" cmd /k "{python_exe} rover.py {nome_rover}"'

        subprocess.Popen(comando, shell=True)

        # Pequeno delay para não "entupir" a rede no arranque
        time.sleep(1)

    print("\nTodos os rovers foram lançados e estão a conectar-se à Nave-Mãe.")

if __name__ == "__main__":
    lancar_frota()