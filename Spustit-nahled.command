#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR/public"
echo "============================================="
echo "  Spouštím lokální náhled TV programu..."
echo "  Adresa: http://localhost:8080"
echo "============================================="
open "http://localhost:8080"
python3 -m http.server 8080
