"""
money — Domain Primitive for Financial Operations

A type-safe, auditable financial primitive that makes floating-point bugs
impossible and provides IFX-compliant governance for AI-assisted finance.

================================================================================
QUICK START
================================================================================

Basic usage:

    from money import Money, Currency
    
    # Create money (never loses precision)
    budget = Money.euro(2026)
    
    # Distribute equally (sum ALWAYS equals original)
    monthly = budget.distribute(12)
    total = sum(monthly, Money.zero(Currency.EUR))  # Always equals budget
    
    # Fiscal operations
    net, vat, gross = Money.euro(100).add_vat(22)
    # Invariant: net + vat == gross (always true)

IFX-compliant AI integration:

    from money import Money, Currency
    from money.ifx import SignedTransaction, Ledger, Gate, QualificationPolicy
    
    # Setup governance
    policy = QualificationPolicy(min_confidence=0.85)
    ledger = Ledger()
    gate = Gate(policy)
    
    # AI suggests amount
    tx = SignedTransaction.from_ai_output(
        amount=Money.euro(500),
        source="claude-3.5-sonnet",
        confidence=0.92,
        rationale="Based on historical Q1 spend"
    )
    
    # Qualify and trace
    decision = gate.evaluate(tx)
    if decision.admitted:
        ledger.append(tx.sign().admit(), decision)

================================================================================
"""

# Core Money type
from .core import (
    Money,
    Currency,
    RoundingMode,
    Allocation,
)

# IFX governance layer
from .ifx import (
    SignedTransaction,
    TransactionMetadata,
    EpistemicStatus,
    QualificationPolicy,
    Gate,
    GateDecision,
    Ledger,
    LedgerEntry,
    ExecutionContext,
    qualify_and_execute,
)

__version__ = "1.0.0"
__author__ = "Ambra Danese"
__license__ = "MIT"

__all__ = [
    # Core
    "Money",
    "Currency", 
    "RoundingMode",
    "Allocation",
    # IFX
    "SignedTransaction",
    "TransactionMetadata",
    "EpistemicStatus",
    "QualificationPolicy",
    "Gate",
    "GateDecision",
    "Ledger",
    "LedgerEntry",
    "ExecutionContext",
    "qualify_and_execute",
]
