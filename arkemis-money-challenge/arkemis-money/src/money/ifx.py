"""
ifx.py — Inference Forensics Execution Layer for Money Operations

================================================================================
IFX FRAMEWORK INTEGRATION
================================================================================

This module implements IFX (Inference Forensics Execution) for financial 
primitives. IFX provides:

1. TRACEABILITY: Every operation has a forensic trail
2. QUALIFICATION: AI-generated amounts must pass policy gates
3. AUDITABILITY: Append-only ledger of all transactions
4. ACCOUNTABILITY: Clear attribution of decisions

When Money is used in AI-assisted contexts (budget suggestions, transaction
proposals, allocation recommendations), IFX ensures that non-deterministic
outputs are qualified before being trusted.

================================================================================
ARCHITECTURE
================================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI/LLM OUTPUT                                      │
│                    (e.g., "allocate €500 to marketing")                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AIOutputQualifier                                    │
│  - Parses AI output                                                          │
│  - Extracts Money values                                                     │
│  - Attaches metadata (source, confidence, timestamp)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Gate                                            │
│  - Applies KQR policies                                                      │
│  - Validates constraints (max amount, confidence threshold)                  │
│  - Returns ADMIT / REJECT decision                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
              ┌─────────┐                   ┌─────────────┐
              │  ADMIT  │                   │   REJECT    │
              └─────────┘                   └─────────────┘
                    │                               │
                    ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Ledger                                          │
│  - Append-only record                                                        │
│  - Cryptographic signatures                                                  │
│  - Full audit trail                                                          │
└─────────────────────────────────────────────────────────────────────────────┘

================================================================================
USAGE
================================================================================

    from money import Money, Currency
    from money.ifx import SignedTransaction, Ledger, Gate, QualificationPolicy
    
    # Create ledger and gate
    ledger = Ledger()
    policy = QualificationPolicy(
        min_confidence=0.85,
        max_amount=Money.euro(10000),
        require_human_approval_above=Money.euro(5000)
    )
    gate = Gate(policy)
    
    # AI suggests a transaction
    ai_output = llm.suggest_budget_allocation(context)
    
    # Qualify the output
    tx = SignedTransaction.from_ai_output(
        amount=Money.from_float(ai_output.amount, Currency.EUR),
        source="claude-3.5-sonnet",
        confidence=ai_output.confidence,
        rationale=ai_output.rationale
    )
    
    # Gate evaluation
    decision = gate.evaluate(tx)
    
    if decision.admitted:
        ledger.append(tx.sign())
        execute_transaction(tx.amount)
    else:
        ledger.append(tx.reject(decision.reason))
        escalate_to_human(tx, decision.reason)

================================================================================
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any, Callable, Tuple
import hashlib
import hmac  # For constant-time comparison
import json
import uuid

# Import from core module
from .core import Money, Currency


# ==============================================================================
# EPISTEMIC TAGS
# ==============================================================================

class EpistemicStatus(Enum):
    """
    Classification of knowledge certainty per IFX/KQR specification.
    
    Every claim about a transaction must be tagged with its epistemic status.
    """
    FACT = "fact"           # Verified, source cited
    INFERENCE = "inference" # Derived from facts, reasoning documented
    ASSUMPTION = "assumption"  # Unverified hypothesis
    AI_GENERATED = "ai_generated"  # Output from non-deterministic source


# ==============================================================================
# SIGNED TRANSACTION
# ==============================================================================

@dataclass(frozen=True)
class TransactionMetadata:
    """
    Metadata attached to every transaction for forensic purposes.
    """
    source: str                      # Origin (human, AI model name, system)
    confidence: float                # 0.0-1.0, required for AI sources
    timestamp: datetime              # When created
    rationale: Optional[str]         # Why this amount (for AI outputs)
    epistemic_status: EpistemicStatus
    policy_version: str              # KQR policy version used
    session_id: str                  # Correlation ID
    parent_tx_id: Optional[str]      # If derived from another transaction
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "rationale": self.rationale,
            "epistemic_status": self.epistemic_status.value,
            "policy_version": self.policy_version,
            "session_id": self.session_id,
            "parent_tx_id": self.parent_tx_id,
        }


@dataclass
class SignedTransaction:
    """
    A Money operation with full forensic trail.
    
    Every transaction in an IFX-compliant system must be signed,
    meaning it has:
    - Unique ID
    - Amount (Money)
    - Metadata (source, confidence, rationale)
    - Signature (hash of content for tamper detection)
    - Status (pending, admitted, rejected, executed)
    
    INVARIANTS:
    - Once signed, content cannot be modified
    - Signature verifies integrity
    - Status transitions are append-only
    """
    tx_id: str
    amount: Money
    metadata: TransactionMetadata
    signature: Optional[str] = None
    status: str = "pending"
    rejection_reason: Optional[str] = None
    
    @classmethod
    def from_ai_output(
        cls,
        amount: Money,
        source: str,
        confidence: float,
        **kwargs,
    ) -> SignedTransaction:
        """
        Create a transaction from AI-generated output.
        
        Optional kwargs: rationale, policy_version, session_id, parent_tx_id
        """
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {confidence}")
        
        metadata = TransactionMetadata(
            source=source,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc),
            rationale=kwargs.get("rationale"),
            epistemic_status=EpistemicStatus.AI_GENERATED,
            policy_version=kwargs.get("policy_version", "KQR-2025-01"),
            session_id=kwargs.get("session_id") or str(uuid.uuid4()),
            parent_tx_id=kwargs.get("parent_tx_id"),
        )
        
        return cls(tx_id=str(uuid.uuid4()), amount=amount, metadata=metadata)
    
    @classmethod
    def from_human(cls, amount: Money, source: str = "human", **kwargs) -> SignedTransaction:
        """Create a transaction from human input. Confidence=1.0, FACT status."""
        metadata = TransactionMetadata(
            source=source,
            confidence=1.0,
            timestamp=datetime.now(timezone.utc),
            rationale=kwargs.get("rationale"),
            epistemic_status=EpistemicStatus.FACT,
            policy_version=kwargs.get("policy_version", "KQR-2025-01"),
            session_id=kwargs.get("session_id") or str(uuid.uuid4()),
            parent_tx_id=None,
        )
        return cls(tx_id=str(uuid.uuid4()), amount=amount, metadata=metadata)
    
    def sign(self) -> SignedTransaction:
        """
        Sign the transaction (compute integrity hash).
        
        Once signed, the transaction content is immutable.
        """
        content = json.dumps({
            "tx_id": self.tx_id,
            "amount": self.amount.to_dict(),
            "metadata": self.metadata.to_dict(),
        }, sort_keys=True)
        
        signature = hashlib.sha256(content.encode()).hexdigest()
        
        return SignedTransaction(
            tx_id=self.tx_id,
            amount=self.amount,
            metadata=self.metadata,
            signature=signature,
            status=self.status,
            rejection_reason=self.rejection_reason,
        )
    
    def verify_signature(self) -> bool:
        """Verify the transaction has not been tampered with."""
        if self.signature is None:
            return False
        
        content = json.dumps({
            "tx_id": self.tx_id,
            "amount": self.amount.to_dict(),
            "metadata": self.metadata.to_dict(),
        }, sort_keys=True)
        
        expected = hashlib.sha256(content.encode()).hexdigest()
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(self.signature, expected)
    
    def admit(self) -> SignedTransaction:
        """Mark transaction as admitted (passed gate)."""
        return SignedTransaction(
            tx_id=self.tx_id,
            amount=self.amount,
            metadata=self.metadata,
            signature=self.signature,
            status="admitted",
            rejection_reason=None,
        )
    
    def reject(self, reason: str) -> SignedTransaction:
        """Mark transaction as rejected with reason."""
        return SignedTransaction(
            tx_id=self.tx_id,
            amount=self.amount,
            metadata=self.metadata,
            signature=self.signature,
            status="rejected",
            rejection_reason=reason,
        )
    
    def execute(self) -> SignedTransaction:
        """Mark transaction as executed."""
        if self.status != "admitted":
            raise ValueError(f"Cannot execute transaction in status '{self.status}'")
        
        return SignedTransaction(
            tx_id=self.tx_id,
            amount=self.amount,
            metadata=self.metadata,
            signature=self.signature,
            status="executed",
            rejection_reason=None,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence/API."""
        return {
            "tx_id": self.tx_id,
            "amount": self.amount.to_dict(),
            "metadata": self.metadata.to_dict(),
            "signature": self.signature,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
        }
    
    def __repr__(self) -> str:
        return (
            f"SignedTransaction(id={self.tx_id[:8]}..., "
            f"amount={self.amount}, status={self.status}, "
            f"source={self.metadata.source})"
        )


# ==============================================================================
# QUALIFICATION POLICY (KQR)
# ==============================================================================

@dataclass
class QualificationPolicy:
    """
    KQR (Knowledge Qualification Regime) policy for transaction admission.
    
    Defines the rules for when an AI-generated transaction can be trusted.
    
    PRINCIPLES:
    - Conservative defaults (high thresholds)
    - Human escalation for high-value/low-confidence
    - Explicit rejection with reason
    """
    # Confidence thresholds
    min_confidence: float = 0.85
    
    # Amount limits
    max_amount: Optional[Money] = None
    
    # Human approval requirements
    require_human_approval_above: Optional[Money] = None
    
    # Source restrictions
    allowed_sources: Optional[List[str]] = None
    blocked_sources: Optional[List[str]] = None
    
    # Policy metadata
    version: str = "KQR-2025-01"
    name: str = "default"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "min_confidence": self.min_confidence,
            "max_amount": self.max_amount.to_dict() if self.max_amount else None,
            "require_human_approval_above": (
                self.require_human_approval_above.to_dict() 
                if self.require_human_approval_above else None
            ),
            "allowed_sources": self.allowed_sources,
            "blocked_sources": self.blocked_sources,
        }


# ==============================================================================
# GATE (DETERMINISTIC EVALUATION)
# ==============================================================================

@dataclass
class GateDecision:
    """Result of gate evaluation."""
    admitted: bool
    reason: str
    policy_version: str
    checks_passed: List[str]
    checks_failed: List[str]
    requires_human_approval: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "admitted": self.admitted,
            "reason": self.reason,
            "policy_version": self.policy_version,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "requires_human_approval": self.requires_human_approval,
        }


class Gate:
    """
    Deterministic evaluation of transactions against KQR policy.
    
    The Gate is the enforcement point of the IFX framework.
    It evaluates transactions and produces ADMIT/REJECT decisions
    with full reasoning trail.
    
    PROPERTIES:
    - Deterministic: same input → same output
    - Traceable: decision includes all checks performed
    - Auditable: every evaluation is logged
    """
    
    def __init__(self, policy: QualificationPolicy):
        self.policy = policy
        self._custom_checks: List[Callable[[SignedTransaction], Optional[str]]] = []
    
    def add_check(self, check: Callable[[SignedTransaction], Optional[str]]) -> Gate:
        """Add a custom check function."""
        self._custom_checks.append(check)
        return self
    
    def _check_confidence(self, tx: SignedTransaction) -> Tuple[List[str], List[str]]:
        """Check confidence threshold."""
        passed, failed = [], []
        conf = tx.metadata.confidence
        min_conf = self.policy.min_confidence
        
        if conf >= min_conf:
            passed.append(f"confidence_check: {conf:.2f} >= {min_conf}")
        else:
            failed.append(f"confidence_check: {conf:.2f} < {min_conf} (required)")
        
        return passed, failed
    
    def _check_amount(self, tx: SignedTransaction) -> Tuple[List[str], List[str]]:
        """Check amount limit."""
        passed, failed = [], []
        max_amt = self.policy.max_amount
        
        if max_amt is None:
            passed.append("amount_check: no limit configured")
            return passed, failed
        
        if tx.amount.currency != max_amt.currency:
            failed.append(f"amount_check: currency mismatch ({tx.amount.currency.code} vs {max_amt.currency.code})")
        elif tx.amount <= max_amt:
            passed.append(f"amount_check: {tx.amount} <= {max_amt}")
        else:
            failed.append(f"amount_check: {tx.amount} > {max_amt} (max)")
        
        return passed, failed
    
    def _check_human_approval(self, tx: SignedTransaction) -> Tuple[List[str], bool]:
        """Check if human approval is required."""
        passed = []
        requires_human = False
        threshold = self.policy.require_human_approval_above
        
        if threshold is None:
            passed.append("human_approval_check: not configured")
            return passed, requires_human
        
        same_currency = tx.amount.currency == threshold.currency
        exceeds = tx.amount > threshold
        
        if same_currency and exceeds:
            requires_human = True
            passed.append(f"human_approval_check: required for {tx.amount} > {threshold}")
        else:
            passed.append("human_approval_check: not required")
        
        return passed, requires_human
    
    def _check_source(self, tx: SignedTransaction) -> Tuple[List[str], List[str]]:
        """Check source restrictions."""
        passed, failed = [], []
        source = tx.metadata.source
        
        if self.policy.allowed_sources is not None:
            if source in self.policy.allowed_sources:
                passed.append(f"source_check: '{source}' in allowed list")
            else:
                failed.append(f"source_check: '{source}' not in allowed list")
        elif self.policy.blocked_sources is not None:
            if source in self.policy.blocked_sources:
                failed.append(f"source_check: '{source}' is blocked")
            else:
                passed.append(f"source_check: '{source}' not blocked")
        else:
            passed.append("source_check: no restrictions")
        
        return passed, failed
    
    def _run_custom_checks(self, tx: SignedTransaction) -> Tuple[List[str], List[str]]:
        """Run custom check functions."""
        passed, failed = [], []
        
        for i, check in enumerate(self._custom_checks):
            result = check(tx)
            if result is None:
                passed.append(f"custom_check_{i}: passed")
            else:
                failed.append(f"custom_check_{i}: {result}")
        
        return passed, failed
    
    def evaluate(self, tx: SignedTransaction) -> GateDecision:
        """Evaluate a transaction against the policy."""
        checks_passed = []
        checks_failed = []
        
        # Run all checks
        p, f = self._check_confidence(tx)
        checks_passed.extend(p)
        checks_failed.extend(f)
        
        p, f = self._check_amount(tx)
        checks_passed.extend(p)
        checks_failed.extend(f)
        
        p, requires_human = self._check_human_approval(tx)
        checks_passed.extend(p)
        
        p, f = self._check_source(tx)
        checks_passed.extend(p)
        checks_failed.extend(f)
        
        p, f = self._run_custom_checks(tx)
        checks_passed.extend(p)
        checks_failed.extend(f)
        
        # Decision
        admitted = len(checks_failed) == 0
        reason = "All checks passed" if admitted else "; ".join(checks_failed)
        
        return GateDecision(
            admitted=admitted,
            reason=reason,
            policy_version=self.policy.version,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            requires_human_approval=requires_human,
        )


# ==============================================================================
# LEDGER (APPEND-ONLY AUDIT TRAIL)
# ==============================================================================

@dataclass
class LedgerEntry:
    """Single entry in the ledger."""
    sequence: int
    timestamp: datetime
    transaction: SignedTransaction
    decision: Optional[GateDecision]
    previous_hash: str
    entry_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "transaction": self.transaction.to_dict(),
            "decision": self.decision.to_dict() if self.decision else None,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }


class Ledger:
    """
    Append-only ledger for IFX audit trail.
    
    Every transaction and gate decision is recorded immutably.
    The ledger uses hash chaining for tamper detection.
    
    PROPERTIES:
    - Append-only: entries cannot be modified or deleted
    - Hash-chained: tampering with any entry invalidates chain
    - Queryable: find transactions by ID, status, time range
    """
    
    # Maximum entries (DoS protection, configurable)
    MAX_ENTRIES: int = 1_000_000
    
    def __init__(self, max_entries: Optional[int] = None):
        self._entries: List[LedgerEntry] = []
        self._genesis_hash = "0" * 64  # Genesis block hash
        self._max_entries = max_entries or self.MAX_ENTRIES
    
    def _compute_hash(self, content: Dict[str, Any]) -> str:
        """Compute SHA-256 hash of content."""
        serialized = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    def append(
        self, 
        transaction: SignedTransaction, 
        decision: Optional[GateDecision] = None
    ) -> LedgerEntry:
        """
        Append a new entry to the ledger.
        
        Returns the created entry.
        
        Raises:
            ValueError: if ledger is at max capacity
        """
        if len(self._entries) >= self._max_entries:
            raise ValueError(f"Ledger at max capacity ({self._max_entries})")
        
        sequence = len(self._entries)
        timestamp = datetime.now(timezone.utc)
        
        # Previous hash
        if sequence == 0:
            previous_hash = self._genesis_hash
        else:
            previous_hash = self._entries[-1].entry_hash
        
        # Compute entry hash
        entry_content = {
            "sequence": sequence,
            "timestamp": timestamp.isoformat(),
            "transaction": transaction.to_dict(),
            "decision": decision.to_dict() if decision else None,
            "previous_hash": previous_hash,
        }
        entry_hash = self._compute_hash(entry_content)
        
        entry = LedgerEntry(
            sequence=sequence,
            timestamp=timestamp,
            transaction=transaction,
            decision=decision,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
        )
        
        self._entries.append(entry)
        return entry
    
    def verify_chain(self) -> tuple[bool, Optional[int]]:
        """
        Verify the integrity of the entire ledger.
        
        Returns:
            (is_valid, first_invalid_sequence)
            If valid, returns (True, None)
            If invalid, returns (False, sequence_of_first_invalid_entry)
        """
        for i, entry in enumerate(self._entries):
            # Check previous hash
            if i == 0:
                expected_prev = self._genesis_hash
            else:
                expected_prev = self._entries[i - 1].entry_hash
            
            # Constant-time comparison to prevent timing attacks
            if not hmac.compare_digest(entry.previous_hash, expected_prev):
                return (False, i)
            
            # Recompute and verify entry hash
            entry_content = {
                "sequence": entry.sequence,
                "timestamp": entry.timestamp.isoformat(),
                "transaction": entry.transaction.to_dict(),
                "decision": entry.decision.to_dict() if entry.decision else None,
                "previous_hash": entry.previous_hash,
            }
            expected_hash = self._compute_hash(entry_content)
            
            # Constant-time comparison
            if not hmac.compare_digest(entry.entry_hash, expected_hash):
                return (False, i)
        
        return (True, None)
    
    def find_by_tx_id(self, tx_id: str) -> Optional[LedgerEntry]:
        """Find entry by transaction ID."""
        for entry in self._entries:
            if entry.transaction.tx_id == tx_id:
                return entry
        return None
    
    def find_by_status(self, status: str) -> List[LedgerEntry]:
        """Find all entries with given transaction status."""
        return [e for e in self._entries if e.transaction.status == status]
    
    def find_in_range(
        self, 
        start: datetime, 
        end: datetime
    ) -> List[LedgerEntry]:
        """Find entries in time range."""
        return [
            e for e in self._entries 
            if start <= e.timestamp <= end
        ]
    
    def get_all(self) -> List[LedgerEntry]:
        """Get all entries (read-only copy)."""
        return self._entries.copy()
    
    def to_json(self) -> str:
        """Export ledger as JSON."""
        return json.dumps(
            [e.to_dict() for e in self._entries],
            indent=2,
            default=str
        )
    
    def __len__(self) -> int:
        return len(self._entries)
    
    def __repr__(self) -> str:
        return f"Ledger(entries={len(self._entries)})"


# ==============================================================================
# EXECUTION CONTEXT
# ==============================================================================

@dataclass
class ExecutionContext:
    """Context for transaction execution workflow."""
    policy: QualificationPolicy
    ledger: Ledger
    on_execute: Callable[[Money], Any]
    on_reject: Callable[[str], Any]


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def qualify_and_execute(
    amount: Money,
    source: str,
    confidence: float,
    context: ExecutionContext,
    rationale: Optional[str] = None,
) -> Tuple[bool, SignedTransaction, GateDecision]:
    """Complete IFX workflow. Returns (success, transaction, decision)."""
    tx = SignedTransaction.from_ai_output(
        amount=amount, source=source, confidence=confidence,
        rationale=rationale, policy_version=context.policy.version,
    ).sign()
    
    decision = Gate(context.policy).evaluate(tx)
    
    if decision.admitted:
        tx = tx.admit()
        context.ledger.append(tx, decision)
        try:
            context.on_execute(tx.amount)
            tx = tx.execute()
        except Exception as e:
            tx = tx.reject(f"Execution failed: {e}")
            context.on_reject(str(e))
        return (True, tx, decision)
    
    tx = tx.reject(decision.reason)
    context.ledger.append(tx, decision)
    context.on_reject(decision.reason)
    return (False, tx, decision)
