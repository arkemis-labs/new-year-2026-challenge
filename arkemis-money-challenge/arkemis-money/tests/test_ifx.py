"""
test_ifx.py — Tests for IFX governance layer

Tests cover:
- SignedTransaction creation and signing
- Gate policy evaluation
- Ledger append-only semantics
- Hash chain integrity
- Full workflow integration
"""

import pytest
from datetime import datetime, timezone, timedelta
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from money import (
    Money,
    Currency,
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


# ==============================================================================
# SignedTransaction Tests
# ==============================================================================

class TestSignedTransaction:
    """Tests for SignedTransaction creation and signing."""
    
    def test_from_ai_output_creates_pending_transaction(self):
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test-model",
            confidence=0.9,
            rationale="Test rationale"
        )
        
        assert tx.status == "pending"
        assert tx.amount == Money.euro(100)
        assert tx.metadata.source == "test-model"
        assert tx.metadata.confidence == 0.9
        assert tx.metadata.epistemic_status == EpistemicStatus.AI_GENERATED
        assert tx.signature is None
    
    def test_from_human_creates_fact_transaction(self):
        tx = SignedTransaction.from_human(
            amount=Money.euro(500),
            source="john.doe",
            rationale="Manual entry"
        )
        
        assert tx.metadata.confidence == 1.0
        assert tx.metadata.epistemic_status == EpistemicStatus.FACT
    
    def test_sign_computes_hash(self):
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.9
        )
        
        signed = tx.sign()
        
        assert signed.signature is not None
        assert len(signed.signature) == 64  # SHA-256 hex
    
    def test_verify_signature_detects_tampering(self):
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.9
        ).sign()
        
        # Valid signature
        assert tx.verify_signature() is True
        
        # Tamper with amount (create new object with different amount)
        tampered = SignedTransaction(
            tx_id=tx.tx_id,
            amount=Money.euro(999),  # Changed!
            metadata=tx.metadata,
            signature=tx.signature,  # Original signature
            status=tx.status
        )
        
        assert tampered.verify_signature() is False
    
    def test_status_transitions(self):
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.9
        ).sign()
        
        # pending -> admitted -> executed
        admitted = tx.admit()
        assert admitted.status == "admitted"
        
        executed = admitted.execute()
        assert executed.status == "executed"
        
        # Cannot execute non-admitted
        with pytest.raises(ValueError):
            tx.execute()
    
    def test_reject_includes_reason(self):
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.5
        ).sign()
        
        rejected = tx.reject("Confidence too low")
        
        assert rejected.status == "rejected"
        assert rejected.rejection_reason == "Confidence too low"
    
    def test_confidence_validation(self):
        with pytest.raises(ValueError):
            SignedTransaction.from_ai_output(
                amount=Money.euro(100),
                source="test",
                confidence=1.5  # Invalid
            )
        
        with pytest.raises(ValueError):
            SignedTransaction.from_ai_output(
                amount=Money.euro(100),
                source="test",
                confidence=-0.1  # Invalid
            )
    
    def test_serialization_round_trip(self):
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.9,
            rationale="Test"
        ).sign()
        
        data = tx.to_dict()
        
        # Verify structure
        assert "tx_id" in data
        assert "amount" in data
        assert "metadata" in data
        assert "signature" in data
        assert data["amount"]["minor_units"] == 10000
        assert data["amount"]["currency"] == "EUR"


# ==============================================================================
# QualificationPolicy Tests
# ==============================================================================

class TestQualificationPolicy:
    """Tests for KQR policy configuration."""
    
    def test_default_policy(self):
        policy = QualificationPolicy()
        
        assert policy.min_confidence == 0.85
        assert policy.max_amount is None
        assert policy.require_human_approval_above is None
    
    def test_custom_policy(self):
        policy = QualificationPolicy(
            min_confidence=0.90,
            max_amount=Money.euro(10000),
            require_human_approval_above=Money.euro(5000),
            allowed_sources=["claude-3", "gpt-4"],
            version="KQR-TEST-01"
        )
        
        assert policy.min_confidence == 0.90
        assert policy.max_amount == Money.euro(10000)


# ==============================================================================
# Gate Tests
# ==============================================================================

class TestGate:
    """Tests for Gate policy evaluation."""
    
    def test_admits_qualifying_transaction(self):
        policy = QualificationPolicy(min_confidence=0.85)
        gate = Gate(policy)
        
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.90
        )
        
        decision = gate.evaluate(tx)
        
        assert decision.admitted is True
        assert len(decision.checks_failed) == 0
    
    def test_rejects_low_confidence(self):
        policy = QualificationPolicy(min_confidence=0.85)
        gate = Gate(policy)
        
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.70  # Below threshold
        )
        
        decision = gate.evaluate(tx)
        
        assert decision.admitted is False
        assert any("confidence" in c for c in decision.checks_failed)
    
    def test_rejects_exceeds_max_amount(self):
        policy = QualificationPolicy(
            min_confidence=0.85,
            max_amount=Money.euro(1000)
        )
        gate = Gate(policy)
        
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(5000),  # Exceeds max
            source="test",
            confidence=0.95
        )
        
        decision = gate.evaluate(tx)
        
        assert decision.admitted is False
        assert any("amount" in c for c in decision.checks_failed)
    
    def test_requires_human_approval_above_threshold(self):
        policy = QualificationPolicy(
            min_confidence=0.85,
            require_human_approval_above=Money.euro(5000)
        )
        gate = Gate(policy)
        
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(7000),  # Above human approval threshold
            source="test",
            confidence=0.95
        )
        
        decision = gate.evaluate(tx)
        
        assert decision.admitted is True  # Still admitted
        assert decision.requires_human_approval is True
    
    def test_source_restrictions_allowed(self):
        policy = QualificationPolicy(
            min_confidence=0.85,
            allowed_sources=["trusted-model"]
        )
        gate = Gate(policy)
        
        # Allowed source
        tx1 = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="trusted-model",
            confidence=0.90
        )
        assert gate.evaluate(tx1).admitted is True
        
        # Not in allowed list
        tx2 = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="unknown-model",
            confidence=0.90
        )
        assert gate.evaluate(tx2).admitted is False
    
    def test_source_restrictions_blocked(self):
        policy = QualificationPolicy(
            min_confidence=0.85,
            blocked_sources=["untrusted-model"]
        )
        gate = Gate(policy)
        
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="untrusted-model",
            confidence=0.90
        )
        
        decision = gate.evaluate(tx)
        assert decision.admitted is False
    
    def test_custom_check(self):
        policy = QualificationPolicy(min_confidence=0.85)
        gate = Gate(policy)
        
        # Add custom check: reject odd amounts
        def no_odd_cents(tx):
            if tx.amount.minor_units % 2 != 0:
                return "Amount must have even cents"
            return None
        
        gate.add_check(no_odd_cents)
        
        # Even amount passes
        tx1 = SignedTransaction.from_ai_output(
            amount=Money.euro_cents(100),
            source="test",
            confidence=0.90
        )
        assert gate.evaluate(tx1).admitted is True
        
        # Odd amount fails
        tx2 = SignedTransaction.from_ai_output(
            amount=Money.euro_cents(101),
            source="test",
            confidence=0.90
        )
        assert gate.evaluate(tx2).admitted is False


# ==============================================================================
# Ledger Tests
# ==============================================================================

class TestLedger:
    """Tests for append-only ledger."""
    
    def test_append_creates_entry(self):
        ledger = Ledger()
        
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.90
        ).sign()
        
        entry = ledger.append(tx)
        
        assert entry.sequence == 0
        assert entry.transaction == tx
        assert len(ledger) == 1
    
    def test_hash_chain(self):
        ledger = Ledger()
        
        for i in range(5):
            tx = SignedTransaction.from_ai_output(
                amount=Money.euro(100 + i),
                source="test",
                confidence=0.90
            ).sign()
            ledger.append(tx)
        
        # Verify chain
        is_valid, invalid_at = ledger.verify_chain()
        assert is_valid is True
        assert invalid_at is None
        
        # Check chain linkage
        entries = ledger.get_all()
        for i in range(1, len(entries)):
            assert entries[i].previous_hash == entries[i-1].entry_hash
    
    def test_find_by_tx_id(self):
        ledger = Ledger()
        
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.90
        ).sign()
        
        ledger.append(tx)
        
        found = ledger.find_by_tx_id(tx.tx_id)
        assert found is not None
        assert found.transaction.tx_id == tx.tx_id
        
        not_found = ledger.find_by_tx_id("nonexistent")
        assert not_found is None
    
    def test_find_by_status(self):
        ledger = Ledger()
        
        # Add various transactions
        admitted = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.90
        ).sign().admit()
        
        rejected = SignedTransaction.from_ai_output(
            amount=Money.euro(200),
            source="test",
            confidence=0.50
        ).sign().reject("Low confidence")
        
        ledger.append(admitted)
        ledger.append(rejected)
        
        admitted_entries = ledger.find_by_status("admitted")
        rejected_entries = ledger.find_by_status("rejected")
        
        assert len(admitted_entries) == 1
        assert len(rejected_entries) == 1
    
    def test_to_json(self):
        ledger = Ledger()
        
        tx = SignedTransaction.from_ai_output(
            amount=Money.euro(100),
            source="test",
            confidence=0.90
        ).sign()
        
        ledger.append(tx)
        
        json_str = ledger.to_json()
        data = json.loads(json_str)
        
        assert len(data) == 1
        assert data[0]["transaction"]["amount"]["minor_units"] == 10000


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestIntegration:
    """End-to-end workflow tests."""
    
    def test_full_workflow_admitted(self):
        # Setup
        policy = QualificationPolicy(min_confidence=0.85)
        ledger = Ledger()
        executed = []
        rejected_reasons = []
        
        context = ExecutionContext(
            policy=policy,
            ledger=ledger,
            on_execute=lambda m: executed.append(m),
            on_reject=lambda r: rejected_reasons.append(r),
        )
        
        # Execute workflow
        success, tx, decision = qualify_and_execute(
            amount=Money.euro(100),
            source="test-model",
            confidence=0.92,
            context=context,
            rationale="Test allocation"
        )
        
        assert success is True
        assert len(executed) == 1
        assert executed[0] == Money.euro(100)
        assert len(ledger) == 1
    
    def test_full_workflow_rejected(self):
        # Setup
        policy = QualificationPolicy(min_confidence=0.85)
        ledger = Ledger()
        executed = []
        rejected_reasons = []
        
        context = ExecutionContext(
            policy=policy,
            ledger=ledger,
            on_execute=lambda m: executed.append(m),
            on_reject=lambda r: rejected_reasons.append(r),
        )
        
        # Execute workflow with low confidence
        success, tx, decision = qualify_and_execute(
            amount=Money.euro(100),
            source="test-model",
            confidence=0.50,  # Below threshold
            context=context,
        )
        
        assert success is False
        assert len(executed) == 0
        assert len(rejected_reasons) == 1
        assert len(ledger) == 1
        assert ledger.get_all()[0].transaction.status == "rejected"
    
    def test_ledger_integrity_after_multiple_operations(self):
        policy = QualificationPolicy(min_confidence=0.80)
        ledger = Ledger()
        
        context = ExecutionContext(
            policy=policy,
            ledger=ledger,
            on_execute=lambda m: None,
            on_reject=lambda r: None,
        )
        
        # Simulate multiple operations
        test_cases = [
            (Money.euro(100), 0.95, True),   # Pass
            (Money.euro(200), 0.70, False),  # Fail confidence
            (Money.euro(300), 0.85, True),   # Pass
            (Money.euro(400), 0.90, True),   # Pass
        ]
        
        for amount, confidence, expected_success in test_cases:
            success, _, _ = qualify_and_execute(
                amount=amount,
                source="test",
                confidence=confidence,
                context=context,
            )
            assert success == expected_success
        
        # Verify ledger integrity
        is_valid, _ = ledger.verify_chain()
        assert is_valid is True
        assert len(ledger) == 4


# ==============================================================================
# Property-Based Tests
# ==============================================================================

try:
    from hypothesis import given, strategies as st, assume
    
    class TestIFXProperties:
        """Property-based tests for IFX invariants."""
        
        @given(
            cents=st.integers(min_value=1, max_value=10**10),
            confidence=st.floats(min_value=0.0, max_value=1.0)
        )
        def test_transaction_signature_deterministic(self, cents, confidence):
            """Same transaction content produces same signature."""
            tx1 = SignedTransaction(
                tx_id="fixed-id",
                amount=Money.euro_cents(cents),
                metadata=TransactionMetadata(
                    source="test",
                    confidence=confidence,
                    timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    rationale=None,
                    epistemic_status=EpistemicStatus.AI_GENERATED,
                    policy_version="test",
                    session_id="fixed-session",
                    parent_tx_id=None
                )
            )
            
            tx2 = SignedTransaction(
                tx_id="fixed-id",
                amount=Money.euro_cents(cents),
                metadata=TransactionMetadata(
                    source="test",
                    confidence=confidence,
                    timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    rationale=None,
                    epistemic_status=EpistemicStatus.AI_GENERATED,
                    policy_version="test",
                    session_id="fixed-session",
                    parent_tx_id=None
                )
            )
            
            assert tx1.sign().signature == tx2.sign().signature
        
        @given(
            threshold=st.floats(min_value=0.01, max_value=0.99),
            actual=st.floats(min_value=0.0, max_value=1.0)
        )
        def test_gate_confidence_decision_consistent(self, threshold, actual):
            """Gate decision on confidence is consistent."""
            policy = QualificationPolicy(min_confidence=threshold)
            gate = Gate(policy)
            
            tx = SignedTransaction.from_ai_output(
                amount=Money.euro(100),
                source="test",
                confidence=actual
            )
            
            decision = gate.evaluate(tx)
            
            if actual >= threshold:
                # Should pass confidence check
                assert not any("confidence" in c and "required" in c 
                             for c in decision.checks_failed)
            else:
                # Should fail confidence check
                assert any("confidence" in c for c in decision.checks_failed)

except ImportError:
    pass  # Hypothesis not installed
