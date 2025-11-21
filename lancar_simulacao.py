import subprocess
import time
import sys
import os

def main():
    print("--- INICIAR SISTEMA DE MISSÃO ESPACIAL ---")

    # Deteta o python atual
    python_exe = sys.executable

    # 1. Lançar a Nave-Mãe
    print(">>> A lançar Nave-Mãe...")
    # Abre em nova janela (Windows cmd)
    subprocess.Popen(f'start "NAVE-MAE" cmd /k "{python_exe} navemae.py"', shell=True)

    time.sleep(2) # Esperar servidor arrancar

    # 2. Lançar 3 Rovers com algum atraso entre eles
    rovers = ["Rover-Alpha", "Rover-Beta", "Rover-Gamma"]

    for nome_rover in rovers:
        print(f">>> A lançar {nome_rover}...")
        subprocess.Popen(f'start "{nome_rover}" cmd /k "{python_exe} rover.py"', shell=True)
        time.sleep(1.5) # Delay para não pedirem todos no milissegundo exato

    print("\nSistema lançado. Verifique as 4 janelas abertas.")

if __name__ == "__main__":
    main()