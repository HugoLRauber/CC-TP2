import subprocess
import sys
import time
import os

def main():
    print(" A LANÇAR FROTA DE ROVERS...")
    
    # IDs dos rovers a lançar
    ids = [1, 2, 3] 
    
    python_exe = sys.executable # Caminho do Python atual

    for rid in ids:
        print(f" > A ativar Rover {rid}...")
        
        # No Windows, abre nova janela com o rover
        if os.name == 'nt':
            cmd = f'start "Rover-{rid}" cmd /k "{python_exe} rover_autonomo.py {rid}"'
        else:
            # Em Linux/Mac, tenta xterm
            cmd = f'xterm -title "Rover-{rid}" -e "{python_exe} rover_autonomo.py {rid}" &'
        
        subprocess.Popen(cmd, shell=True)
        time.sleep(1) # Intervalo para não atropelar portas

    print("\n Frota lançada! Verifica as novas janelas.")

if __name__ == "__main__":
    main()
