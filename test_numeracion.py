#!/usr/bin/env python3
"""
Script de prueba para verificar el sistema de numeración secuencial
"""
from pathlib import Path
from core.pipeline.processor import NarrativeProcessor
from core.models.configs import ProcessingConfig, RewriteConfig
from core.repository.csv_repository import CSVNarrativeRepository
from core.repository.file_manager import FileManager

# Configuración básica
pconf = ProcessingConfig(
    run_dir=Path("runs/test"),
    bucket="test-bucket",
    s3_prefix="test/",
    region="us-east-1",
    enable_aws=False,
)

rconf = RewriteConfig(
    model_name="gpt-4",
    min_words=240,
    max_words=260,
    language="ES",
    max_retries=3,
    prompt_template=None,
)

repo = CSVNarrativeRepository(Path("data/narratives.csv"))
fm = FileManager(Path("."), "test_user")

# Mock de procesadores
class MockProcessor:
    def download(self, *args, **kwargs): pass
    def upload(self, *args, **kwargs): pass
    def transcribe(self, *args, **kwargs): pass
    def rewrite(self, *args, **kwargs): pass
    def build(self, *args, **kwargs): pass

mock = MockProcessor()

proc = NarrativeProcessor(pconf, rconf, repo, fm, mock, mock, mock, mock, mock)

print("=== PRUEBA DE RESERVA DE NÚMEROS SECUENCIALES ===\n")

# Simular el usuario 'a' que ya tiene 5 narrativas
print("Usuario 'a' tiene actualmente:")
narrativas_a = list(repo.list(user_id="a"))
for n in sorted(narrativas_a, key=lambda x: x.seq):
    print(f"  Narrativa #{n.seq}")

print(f"\nTotal: {len(narrativas_a)} narrativas\n")

# Probar reserva de números
print("🧪 Reservando 3 números consecutivos...")
nums = proc._reserve_sequential_numbers("a", 3)
print(f"✅ Números reservados: {nums}")
print(f"   Esperado: [6, 7, 8]")
print(f"   ✓ CORRECTO" if nums == [6, 7, 8] else f"   ✗ ERROR")

print("\n🧪 Reservando 5 números más...")
nums2 = proc._reserve_sequential_numbers("a", 5)
print(f"✅ Números reservados: {nums2}")
print(f"   Esperado: [6, 7, 8, 9, 10]")
print(f"   ✓ CORRECTO" if nums2 == [6, 7, 8, 9, 10] else f"   ✗ ERROR")

# Probar para usuario nuevo
print("\n🧪 Reservando números para usuario nuevo 'test_user'...")
nums3 = proc._reserve_sequential_numbers("test_user", 3)
print(f"✅ Números reservados: {nums3}")
print(f"   Esperado: [1, 2, 3]")
print(f"   ✓ CORRECTO" if nums3 == [1, 2, 3] else f"   ✗ ERROR")

print("\n=== PRUEBA COMPLETADA ===")
