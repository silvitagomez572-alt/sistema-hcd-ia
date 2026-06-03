#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')
IP=${IP:-localhost}

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║           Sistema HCD IA — Estado de servicios       ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

api_state=$(systemctl --user is-active hcd-api.service 2>/dev/null || echo "inactivo")
front_state=$(systemctl --user is-active hcd-frontend.service 2>/dev/null || echo "inactivo")

echo "  FastAPI   [${api_state}]    → http://${IP}:8000"
echo "  Streamlit [${front_state}]  → http://${IP}:8501"
echo "  Docs API                    → http://${IP}:8000/docs"
echo ""

if [[ "$api_state" != "active" || "$front_state" != "active" ]]; then
    echo "  Iniciando servicios caídos..."
    [[ "$api_state"   != "active" ]] && systemctl --user start hcd-api.service
    [[ "$front_state" != "active" ]] && systemctl --user start hcd-frontend.service
    sleep 3
    api_state=$(systemctl --user is-active hcd-api.service 2>/dev/null)
    front_state=$(systemctl --user is-active hcd-frontend.service 2>/dev/null)
    echo ""
    echo "  FastAPI   [${api_state}]    → http://${IP}:8000"
    echo "  Streamlit [${front_state}]  → http://${IP}:8501"
    echo ""
fi
