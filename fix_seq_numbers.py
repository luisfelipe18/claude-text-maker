#!/usr/bin/env python3
"""
Script para corregir la numeración de secuencias duplicadas en narratives.csv
"""
from pathlib import Path
from core.repository.csv_repository import CSVNarrativeRepository
from datetime import datetime

def fix_sequence_numbers():
    """Corrige los números de secuencia duplicados por usuario"""

    repo = CSVNarrativeRepository(Path('data/narratives.csv'))

    # Obtener todas las narrativas agrupadas por usuario
    all_narratives = list(repo.list())

    # Agrupar por usuario
    users = {}
    for n in all_narratives:
        if n.user_id not in users:
            users[n.user_id] = []
        users[n.user_id].append(n)

    print("=== CORRECCIÓN DE NÚMEROS DE SECUENCIA ===\n")

    for user_id, narratives in users.items():
        print(f"Usuario: {user_id}")
        print(f"  Total narrativas: {len(narratives)}")

        # Ordenar por fecha de creación
        narratives.sort(key=lambda n: n.created_at if n.created_at else datetime.min)

        # Verificar si hay duplicados
        seqs = [n.seq for n in narratives if n.seq > 0]
        has_duplicates = len(seqs) != len(set(seqs))

        if has_duplicates or any(n.seq == 0 for n in narratives):
            print(f"  ⚠️  Detectados problemas de numeración - corrigiendo...")

            # Reasignar secuencias
            for idx, narrative in enumerate(narratives, start=1):
                old_seq = narrative.seq
                narrative.seq = idx

                if old_seq != idx:
                    print(f"    {narrative.id}: seq {old_seq} → {idx}")
                    repo.update(narrative)

            print(f"  ✅ Narrativas renumeradas de 1 a {len(narratives)}")
        else:
            print(f"  ✅ Numeración correcta")

        print()

    print("=== CORRECCIÓN COMPLETADA ===\n")

    # Verificar el resultado
    print("=== VERIFICACIÓN FINAL ===\n")
    for user_id in users.keys():
        narratives = list(repo.list(user_id=user_id))
        narratives.sort(key=lambda n: n.seq)
        print(f"Usuario: {user_id}")
        for n in narratives:
            status = n.status.value if hasattr(n.status, 'value') else str(n.status)
            platform = n.platform.value if hasattr(n.platform, 'value') else str(n.platform)
            created = n.created_at.strftime('%Y-%m-%d %H:%M') if n.created_at else "Sin fecha"
            print(f"  #{n.seq:03d} | {platform:10s} | {status:15s} | {created}")
        print()

if __name__ == "__main__":
    fix_sequence_numbers()
