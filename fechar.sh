#!/bin/bash

echo "================================================"
echo "          A TERMINAR TODAS AS MISSOES"
echo "================================================"

echo ""
echo "1. A matar processos Python..."

# Mata a Nave Mãe
pkill -f "python3 navemae.py" && echo " - Nave-Mãe terminada."

# Mata os Rovers
pkill -f "python3 rover_autonomo.py" && echo " - Rovers terminados."

# Mata o Ground Control (Terminal)
pkill -f "python3 GroundControl.py" && echo " - Ground Control terminado."

# Opcional: Mata o Firefox aberto pelo script (cuidado se tiver outros abertos)
pkill -f "firefox" && echo " - Firefox fechado."

echo ""
echo "2. A limpar processos orfãos..."
# Mata qualquer python solto na pasta src
pkill -f "src/"

echo ""
echo "================================================"
echo "              LIMPEZA CONCLUIDA."
echo "================================================"
