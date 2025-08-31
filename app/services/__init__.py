# app/services/__init__.py

from .payroll_service import (
    process_assignments_batch,
    update_or_create_contract_calculations,  # OBSOLÈTE - conservé pour fallback
    get_contract_summary,
    recalculate_all_contracts
)

__all__ = [
    'process_assignments_batch',
    'update_or_create_contract_calculations',  # OBSOLÈTE
    'get_contract_summary', 
    'recalculate_all_contracts'
]
