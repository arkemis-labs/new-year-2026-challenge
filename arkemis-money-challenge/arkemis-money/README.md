# Money

> Domain primitive that makes financial bugs impossible.

```python
❌  2026.0 / 12 * 12  →  2025.9999999999998

✅  Money.euro(2026).distribute(12)  →  sum always equals 2026.00 EUR
```

---

## The Problem

IEEE 754 floating-point arithmetic works exactly as designed.
The problem is using it for money.

```python
>>> 2026.0 / 12 * 12
2025.9999999999998

>>> sum([2026.0 / 12] * 12)
2025.9999999999995
```

This isn't a rounding error to catch. It's a design flaw to prevent.

## The Solution

Money is not a number. It's a **domain primitive** with rules:

- Cannot mix currencies (EUR + USD = TypeError)
- Fixed precision per currency (EUR=2, JPY=0, KWD=3)
- Distribution preserves total (mathematical proof, not hope)
- Immutable (no state corruption)

```python
from money import Money, Currency

budget = Money.euro(2026)
monthly = budget.distribute(12)

# This is PROVEN, not tested
assert sum(monthly, Money.zero(Currency.EUR)) == budget
```

## Why This Exists

In 2025, every fintech will use AI to suggest transactions.

Who guarantees those suggestions are correct?
Who traces the decision?
Who answers the auditor?

This library provides:

1. **Structural correctness** — bugs are impossible, not just unlikely
2. **IFX compliance** — governance layer for AI-assisted finance
3. **Audit trail** — every operation is traceable and signed

---

## Quick Start

### Installation

```bash
pip install money-type  # Coming soon
# For now:
git clone https://github.com/ambradan/arkemis-money
```

### Basic Usage

```python
from money import Money, Currency

# Create (always precise)
price = Money.euro(100)
price_cents = Money.euro_cents(10050)  # 100.50 EUR
from_legacy = Money.from_float(99.99, Currency.EUR)  # Explicit conversion

# Distribute (sum ALWAYS equals original)
budget = Money.euro(2026)
monthly = budget.distribute(12)
# [168.84, 168.84, 168.84, 168.84, 168.83, 168.83, 168.83, 168.83, 168.83, 168.83, 168.83, 168.83]

# Fiscal operations (invariants guaranteed)
net, vat, gross = price.add_vat(22)
assert net + vat == gross  # Always true

# Type safety
eur = Money.euro(100)
usd = Money.usd(100)
eur + usd  # TypeError: cannot mix currencies
eur + 50.0  # TypeError: use Money.from_float() explicitly
```

### IFX-Compliant AI Integration

```python
from money import Money, Currency
from money.ifx import SignedTransaction, Ledger, Gate, QualificationPolicy

# Define policy
policy = QualificationPolicy(
    min_confidence=0.85,
    max_amount=Money.euro(10000),
    require_human_approval_above=Money.euro(5000)
)

# Setup
ledger = Ledger()
gate = Gate(policy)

# AI suggests amount
tx = SignedTransaction.from_ai_output(
    amount=Money.euro(500),
    source="claude-3.5-sonnet",
    confidence=0.92,
    rationale="Based on Q1 historical patterns"
)

# Qualify
decision = gate.evaluate(tx)

if decision.admitted:
    ledger.append(tx.sign().admit(), decision)
    execute(tx.amount)
else:
    ledger.append(tx.sign().reject(decision.reason), decision)
    escalate(decision.reason)

# Audit
print(ledger.to_json())
```

---

## Formal Guarantees

### distribute(n) Invariant

**Theorem**: For any Money M and integer n > 0:
```
sum(M.distribute(n)) == M
```

**Proof**:

Let M = minor_units, n > 0

```
base = M // n         (integer division)
remainder = M % n     (modulo)

By definition: M = n × base + remainder, where 0 ≤ remainder < n

Distribution produces:
  - remainder parts of value (base + 1)
  - (n - remainder) parts of value base

Sum = remainder × (base + 1) + (n - remainder) × base
    = remainder × base + remainder + n × base - remainder × base
    = n × base + remainder
    = M  ∎
```

**Verification**: 1000+ random test cases via Hypothesis (property-based testing)

### Type Safety

- `Money + Money` → Only if same currency
- `Money + float` → TypeError (explicit conversion required)
- `Money × int` → Valid (quantity multiplication)
- `Money × float` → TypeError (use apply_percentage)

### Serialization

```python
# Always integers, never float
{"minor_units": 202600, "currency": "EUR"}

# Never this (precision loss risk)
{"amount": 2026.00, "currency": "EUR"}
```

---

## Comparison

| Approach | Prevents bug | Type-safe | Multi-currency | Invariant proven | AI-ready |
|----------|--------------|-----------|----------------|------------------|----------|
| float | ❌ | ❌ | ❌ | ❌ | ❌ |
| Decimal | ✅ | ❌ | ❌ | ❌ | ❌ |
| int (cents) | ✅ | ❌ | ❌ | ❌ | ❌ |
| py-moneyed | ✅ | Partial | ✅ | ❌ | ❌ |
| **This** | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Application                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         Money                                │
│  - Immutable value object                                    │
│  - Integer-only internal representation                     │
│  - Currency-aware operations                                │
│  - Proven distribution algorithm                            │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────────┐
│     Direct Usage        │     │    IFX Layer (AI contexts)  │
│  - Budget calculations  │     │  - SignedTransaction        │
│  - Invoice totals       │     │  - Gate (policy evaluation) │
│  - VAT/discount         │     │  - Ledger (audit trail)     │
└─────────────────────────┘     └─────────────────────────────┘
```

---

## Who This Is For

- **Fintech building AI features**: Your LLM suggests transactions. How do you audit them?
- **Regulated industries**: Healthcare, legal, PA — anywhere money flows and accountability matters
- **Anyone tired of "it works in my tests"**: You want provable guarantees, not hope

---

## Project Status

| Component | Status |
|-----------|--------|
| Money type | ✅ Production-ready |
| Property-based tests | ✅ 1000+ cases |
| IFX integration | ✅ Complete |
| KQR policy engine | ✅ Complete |
| PyPI package | 🔄 Coming soon |

---

## Running Tests

```bash
# Install dependencies
pip install pytest hypothesis

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/money --cov-report=html
```

---

## Examples

```bash
# Challenge solution demo
python examples/challenge_solution.py

# IFX governance workflow demo
python examples/ifx_governance_demo.py
```

---

## Part of a Larger Initiative

This is the first component of **IFX/KQR** — a governance framework for AI-assisted decision-making in regulated environments.

| Version | Component | Status |
|---------|-----------|--------|
| 1.0 | Money type | ✅ This release |
| 1.1 | IFX integration | ✅ This release |
| 2.0 | IBAN, BIC, SWIFT primitives | Planned |
| 2.1 | Multi-currency conversion | Planned |
| 3.0 | Cross-system reconciliation | Research |

Framework: [IFX-vs-KQR](https://github.com/ambradan/IFX-vs-KQR)

---

## Security Considerations

- **No floating point in serialization**: Prevents roundtrip corruption
- **Type-safe operations**: Prevents currency mixing attacks
- **Immutable**: Prevents state manipulation
- **Signed transactions**: Tamper detection via hash chain
- **Audit-ready**: Full forensic trail for compliance

---

## License

MIT

---

## Contributing

Issues and PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

> In regulated environments, the absence of qualification is itself a risk.
> 
> — IFX/KQR Specification

This library doesn't just fix floating-point bugs.
It provides **auditable, AI-safe financial primitives**
for systems where errors are not acceptable.
