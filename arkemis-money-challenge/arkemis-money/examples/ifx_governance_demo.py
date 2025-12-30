#!/usr/bin/env python3
"""
ifx_governance_demo.py — IFX Transaction Qualification Workflow

================================================================================
SCENARIO
================================================================================

Financial operations from non-deterministic sources (external systems, 
ML models, third-party APIs) require qualification before execution.

PROBLEM:
- Non-deterministic sources produce varying outputs
- Financial decisions require accountability
- Errors propagate (wrong allocation → cascading issues)
- Auditors ask: "Why this number? Who approved it? What was the policy?"

SOLUTION (IFX Framework):
- Every proposed operation becomes a SignedTransaction
- Gate evaluates against KQR policy (deterministic)
- Only qualified operations execute
- Full audit trail in append-only Ledger

================================================================================
THIS DEMO
================================================================================

Simulates a workflow where proposed budget allocations are:
1. Wrapped in SignedTransaction with metadata
2. Evaluated against configurable policy thresholds
3. Admitted or rejected with full reasoning
4. Logged to tamper-evident ledger

The source of proposals is irrelevant — what matters is the governance layer.

================================================================================
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Optional
import random

# Add src to path for demo
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from money import (
    Money, 
    Currency,
    SignedTransaction,
    QualificationPolicy,
    Gate,
    Ledger,
    EpistemicStatus,
)


# ==============================================================================
# MOCK PROPOSAL SOURCE
# ==============================================================================

@dataclass
class BudgetProposal:
    """A proposed budget allocation from an external source."""
    department: str
    amount_eur: float
    confidence: float
    rationale: str


class BudgetProposalSource:
    """
    Simulates an external source proposing budget allocations.
    
    In production, this could be:
    - An ML forecasting model
    - A third-party planning system
    - A rules engine
    - Manual input from a non-authoritative source
    
    The IFX layer doesn't care about the source type —
    it cares about qualification.
    """
    
    def __init__(self, source_id: str = "external-planning-system"):
        self.source_id = source_id
    
    def get_proposals(self, total_budget: Money, departments: List[str]) -> List[BudgetProposal]:
        """
        Generate budget allocation proposals.
        
        Returns proposals with varying confidence levels to demonstrate
        the Gate's filtering behavior.
        """
        proposals = [
            BudgetProposal(
                department="Engineering",
                amount_eur=45000.00,
                confidence=0.94,  # High confidence — passes
                rationale="Historical spend + 10% growth projection. Strong correlation with Q1 patterns."
            ),
            BudgetProposal(
                department="Marketing", 
                amount_eur=28000.00,
                confidence=0.78,  # Below threshold — FAILS
                rationale="Campaign budget estimate. Lower confidence due to market uncertainty."
            ),
            BudgetProposal(
                department="Operations",
                amount_eur=15000.00,
                confidence=0.91,  # Passes
                rationale="Fixed costs + seasonal adjustment. Highly predictable."
            ),
            BudgetProposal(
                department="R&D",
                amount_eur=62000.00,  # Exceeds max_amount — FAILS
                confidence=0.89,
                rationale="New project allocation. Includes prototype budget."
            ),
        ]
        
        return proposals


# ==============================================================================
# IFX PROCESSOR
# ==============================================================================

class TransactionProcessor:
    """
    Processes proposed operations through IFX governance.
    
    Flow:
    1. Receive proposals from any source
    2. Convert each to SignedTransaction
    3. Evaluate against KQR policy via Gate
    4. Execute admitted transactions
    5. Log everything to Ledger
    """
    
    def __init__(self, policy: QualificationPolicy):
        self.policy = policy
        self.gate = Gate(policy)
        self.ledger = Ledger()
        self.executed_allocations: dict[str, Money] = {}
        self.rejected_allocations: dict[str, str] = {}
    
    def process_proposal(
        self, 
        proposal: BudgetProposal,
        source_id: str
    ) -> tuple[bool, str]:
        """
        Process a single proposal through IFX pipeline.
        
        Returns:
            (admitted: bool, message: str)
        """
        # Step 1: Convert to Money
        amount = Money.from_float(proposal.amount_eur, Currency.EUR)
        
        # Step 2: Create SignedTransaction
        tx = SignedTransaction.from_ai_output(
            amount=amount,
            source=source_id,
            confidence=proposal.confidence,
            rationale=proposal.rationale,
            policy_version=self.policy.version,
        )
        
        # Step 3: Sign (compute integrity hash)
        tx = tx.sign()
        
        # Step 4: Gate evaluation
        decision = self.gate.evaluate(tx)
        
        # Step 5: Act on decision
        if decision.admitted:
            if decision.requires_human_approval:
                # In production: queue for human review
                tx = tx.admit()
                self.ledger.append(tx, decision)
                return (True, f"✓ ADMITTED (pending human approval): {proposal.department} = {amount}")
            else:
                # Auto-execute
                tx = tx.admit().execute()
                self.ledger.append(tx, decision)
                self.executed_allocations[proposal.department] = amount
                return (True, f"✓ EXECUTED: {proposal.department} = {amount}")
        else:
            tx = tx.reject(decision.reason)
            self.ledger.append(tx, decision)
            self.rejected_allocations[proposal.department] = decision.reason
            return (False, f"✗ REJECTED: {proposal.department} — {decision.reason}")
    
    def get_audit_report(self) -> str:
        """Generate human-readable audit report."""
        lines = []
        lines.append("=" * 70)
        lines.append("IFX AUDIT REPORT")
        lines.append("=" * 70)
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"Policy: {self.policy.name} (v{self.policy.version})")
        lines.append(f"Total entries: {len(self.ledger)}")
        lines.append("")
        
        # Ledger integrity
        is_valid, invalid_at = self.ledger.verify_chain()
        if is_valid:
            lines.append("🔒 LEDGER INTEGRITY: VERIFIED")
        else:
            lines.append(f"⚠️  LEDGER INTEGRITY: COMPROMISED at entry {invalid_at}")
        lines.append("")
        
        # Summary
        executed = self.ledger.find_by_status("executed")
        rejected = self.ledger.find_by_status("rejected")
        lines.append(f"Executed: {len(executed)}")
        lines.append(f"Rejected: {len(rejected)}")
        lines.append("")
        
        # Detail
        lines.append("-" * 70)
        lines.append("TRANSACTION LOG")
        lines.append("-" * 70)
        
        for entry in self.ledger.get_all():
            tx = entry.transaction
            lines.append(f"")
            lines.append(f"[{entry.sequence}] {tx.status.upper()}")
            lines.append(f"    TX ID: {tx.tx_id[:16]}...")
            lines.append(f"    Amount: {tx.amount}")
            lines.append(f"    Source: {tx.metadata.source}")
            lines.append(f"    Confidence: {tx.metadata.confidence:.0%}")
            lines.append(f"    Rationale: {tx.metadata.rationale[:60]}...")
            if tx.rejection_reason:
                lines.append(f"    Rejection: {tx.rejection_reason}")
            if entry.decision:
                lines.append(f"    Checks passed: {len(entry.decision.checks_passed)}")
                lines.append(f"    Checks failed: {len(entry.decision.checks_failed)}")
            lines.append(f"    Entry hash: {entry.entry_hash[:16]}...")
        
        lines.append("")
        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)
        
        return "\n".join(lines)


# ==============================================================================
# MAIN DEMO
# ==============================================================================

def main():
    print("=" * 70)
    print("IFX GOVERNANCE DEMO — Transaction Qualification Workflow")
    print("=" * 70)
    print()
    
    # Define KQR policy
    print("📋 POLICY CONFIGURATION (KQR)")
    print("-" * 70)
    policy = QualificationPolicy(
        min_confidence=0.85,  # Reject below 85% confidence
        max_amount=Money.euro(50000),  # Reject above €50,000
        require_human_approval_above=Money.euro(40000),  # Human review above €40k
        version="KQR-2025-01",
        name="Q1-Budget-Policy",
    )
    print(f"  Min confidence: {policy.min_confidence:.0%}")
    print(f"  Max amount: {policy.max_amount}")
    print(f"  Human approval above: {policy.require_human_approval_above}")
    print()
    
    # Initialize source and processor
    source = BudgetProposalSource(source_id="planning-system-v2")
    processor = TransactionProcessor(policy)
    
    # Get proposals
    print("📥 INCOMING PROPOSALS")
    print("-" * 70)
    total_budget = Money.euro(150000)
    departments = ["Engineering", "Marketing", "Operations", "R&D"]
    
    proposals = source.get_proposals(total_budget, departments)
    for p in proposals:
        print(f"  {p.department}: €{p.amount_eur:,.2f} (confidence: {p.confidence:.0%})")
    print()
    
    # Process through IFX
    print("⚙️  GATE EVALUATION")
    print("-" * 70)
    for proposal in proposals:
        admitted, message = processor.process_proposal(proposal, source.source_id)
        print(f"  {message}")
    print()
    
    # Summary
    print("📊 EXECUTION SUMMARY")
    print("-" * 70)
    total_executed = sum(
        processor.executed_allocations.values(), 
        Money.zero(Currency.EUR)
    )
    print(f"  Total executed: {total_executed}")
    print(f"  Executed allocations: {len(processor.executed_allocations)}")
    print(f"  Rejected allocations: {len(processor.rejected_allocations)}")
    print()
    
    for dept, amount in processor.executed_allocations.items():
        print(f"    ✓ {dept}: {amount}")
    for dept, reason in processor.rejected_allocations.items():
        print(f"    ✗ {dept}: {reason[:50]}...")
    print()
    
    # Audit report
    print(processor.get_audit_report())
    
    # Demonstrate ledger integrity
    print()
    print("🔐 TAMPER DETECTION")
    print("-" * 70)
    print("  Verifying ledger integrity...")
    is_valid, _ = processor.ledger.verify_chain()
    print(f"  Result: {'✓ VALID — no tampering detected' if is_valid else '✗ TAMPERED'}")
    print()
    
    # Export ledger
    print("💾 LEDGER EXPORT (JSON)")
    print("-" * 70)
    ledger_json = processor.ledger.to_json()
    print(f"  Ledger size: {len(ledger_json)} bytes")
    print(f"  First 500 chars:")
    print(ledger_json[:500])
    print("  ...")


if __name__ == "__main__":
    main()
