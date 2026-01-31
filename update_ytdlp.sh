#!/bin/bash
# Script para actualizar yt-dlp y solucionar errores HTTP 403

echo "🔄 Actualizando yt-dlp..."
pip install --upgrade yt-dlp

echo ""
echo "✅ Actualización completada"
echo ""
echo "Versión instalada:"
python3 -m yt_dlp --version

echo ""
echo "💡 Si sigues teniendo errores HTTP 403 con Facebook:"
echo "   1. Verifica que el video sea público"
echo "   2. Intenta con otro video para descartar problemas específicos"
echo "   3. Facebook puede estar bloqueando descargas masivas temporalmente"
