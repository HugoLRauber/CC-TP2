#!/bin/bash

# --- 1. CONFIGURAÇÃO ---
# Define a pasta base para poder criar a pasta logs ao lado da src
BASE_DIR="/home/core/Desktop/TP2"
PROJ_DIR="$BASE_DIR/src"
LOG_DIR="$BASE_DIR/logs"

IP_NAVE="10.0.0.10"
IP_NAVE_TERRA="10.0.4.10"

# --- 2. PREPARAÇÃO DOS LOGS ---
# Cria a pasta logs se não existir
mkdir -p "$LOG_DIR"

# Gera o carimbo de tempo (Ex: 2024-01-05_15-30-00)
TIMESTAMP=$(date "+%Y-%m-%d_%H-%M-%S")

# --- 3. FUNÇÃO DE LIMPEZA ---
cleanup() {
    echo ""
    echo " A RECEBER SINAL DE PARAGEM..."
    kill 0 2>/dev/null
    pkill -f "python3 navemae.py"
    pkill -f "python3 rover_autonomo.py"
    pkill -f "python3 GroundControl.py"
    echo " Simulação terminada."
    exit
}
trap cleanup SIGINT

# --- 4. INÍCIO DA SIMULAÇÃO ---
echo " A INICIAR SIMULAÇÃO..."
echo " Os logs serão guardados em: $LOG_DIR"
echo " Carimbo da sessão: $TIMESTAMP"

SESSION_DIR=$(ls -dt /tmp/pycore* | head -1)
if [ -z "$SESSION_DIR" ]; then
    echo " ERRO: Nenhuma simulação CORE detetada! Inicie a simulação (Botão Verde)."
    exit 1
fi
echo " Sessão encontrada: $SESSION_DIR"

# Função auxiliar
run_in_node() {
    vcmd -c "$SESSION_DIR/$1" -- bash -c "$2" &
}

xhost +local:root > /dev/null 2>&1

# --- 5. LANÇAR PROCESSOS (COM LOGS DATADOS) ---
# Adicionei a flag -u ao python para o log ser escrito instantaneamente

echo " > A arrancar Nave-Mãe..."
LOG_FILE="$LOG_DIR/navemae_$TIMESTAMP.log"
run_in_node "navemae" "cd $PROJ_DIR && python3 -u navemae.py > \"$LOG_FILE\" 2>&1"
sleep 2

echo " > A arrancar Rover Alpha..."
LOG_FILE="$LOG_DIR/rover_alpha_$TIMESTAMP.log"
run_in_node "Rover-Alpha" "cd $PROJ_DIR && python3 -u rover_autonomo.py 1 $IP_NAVE > \"$LOG_FILE\" 2>&1"

echo " > A arrancar Rover Beta..."
LOG_FILE="$LOG_DIR/rover_beta_$TIMESTAMP.log"
run_in_node "Rover-Beta" "cd $PROJ_DIR && python3 -u rover_autonomo.py 2 $IP_NAVE > \"$LOG_FILE\" 2>&1"

echo " > A arrancar Rover Gamma..."
LOG_FILE="$LOG_DIR/rover_gamma_$TIMESTAMP.log"
run_in_node "Rover-Gamma" "cd $PROJ_DIR && python3 -u rover_autonomo.py 3 $IP_NAVE > \"$LOG_FILE\" 2>&1"

# --- 6. ABRIR DASHBOARDS ---
echo " > A abrir Dashboard..."
run_in_node "groundcontrol" "DISPLAY=:0 firefox http://$IP_NAVE_TERRA:8080/groundcontrol &"
sleep 2
run_in_node "groundcontrol" "DISPLAY=:0 firefox http://$IP_NAVE_TERRA:8080/navemae &"

echo ""
echo " SISTEMA A CORRER!"
echo " Logs disponíveis na pasta 'logs'."
echo " Pressione [CTRL + C] neste terminal para fechar TUDO."

wait
