# Roadmap

This document outlines the development roadmap for the Money domain primitive and the broader IFX/KQR ecosystem.

---

## Vision

Build the foundational infrastructure for **AI-safe financial operations** in regulated environments.

When AI systems suggest financial decisions, there must be:
- **Traceability**: Where did this number come from?
- **Accountability**: Who approved it?
- **Auditability**: Can we reconstruct the decision chain?

This project provides the primitives that make those guarantees possible.

---

## Current Release: v1.0

### ✅ Delivered

| Component | Description | Status |
|-----------|-------------|--------|
| Money type | Immutable, type-safe monetary value object | Complete |
| Multi-currency | EUR, USD, GBP, JPY, KWD, BTC with correct precision | Complete |
| Distribution | Proven-correct allocation algorithm | Complete |
| Fiscal ops | VAT add/extract, discount with invariants | Complete |
| Property tests | 1000+ random cases via Hypothesis | Complete |
| IFX layer | SignedTransaction, Gate, Ledger | Complete |
| KQR policies | Confidence thresholds, amount limits, source restrictions | Complete |

---

## v1.1 — Enhanced IFX (Q1 2025)

### Planned Features

| Feature | Description | Priority |
|---------|-------------|----------|
| Persistent ledger | File/DB-backed ledger with recovery | High |
| Policy DSL | Declarative policy definition (YAML/JSON) | High |
| Human approval workflow | Queue and approval system integration | High |
| Ledger export | CSV, Parquet for analytics | Medium |
| Metrics | Prometheus/OpenTelemetry integration | Medium |
| REST API | FastAPI wrapper for IFX operations | Low |

### Technical Debt

- [ ] Add async support for Gate evaluation
- [ ] Implement ledger compaction (archival of old entries)
- [ ] Add policy versioning with migration support

---

## v2.0 — Financial Primitives Expansion (Q2 2025)

### New Domain Primitives

| Primitive | Description | Use Case |
|-----------|-------------|----------|
| IBAN | International bank account number | EU payments |
| BIC/SWIFT | Bank identifier codes | International transfers |
| AccountNumber | Generic account with validation | Multi-system integration |
| Percentage | Type-safe percentages (0-100 or 0-1) | Interest, tax rates |
| ExchangeRate | Currency pair with timestamp | Forex |

### Currency Conversion

```python
# Planned API
from money import Money, ExchangeRate, convert

rate = ExchangeRate(EUR=1.0, USD=1.08, timestamp=now())
eur = Money.euro(100)
usd = convert(eur, Currency.USD, rate)

# With IFX tracking
tx = SignedConversion.from_rate(
    source_amount=eur,
    target_currency=Currency.USD,
    rate=rate,
    source="ecb-rates",
    confidence=0.99  # Market rate confidence
)
```

### Multi-Currency Distribution

```python
# Distribute across currencies
portfolio = Portfolio([
    (Money.euro(10000), 0.5),    # 50% EUR
    (Money.usd(5000), 0.3),      # 30% USD
    (Money.gbp(2000), 0.2),      # 20% GBP
])

allocation = portfolio.distribute_by_weight(weights)
```

---

## v2.1 — Advanced Validation (Q3 2025)

### Payment Validation

| Feature | Description |
|---------|-------------|
| SEPA validation | IBAN/BIC EU compliance |
| ABA routing | US bank routing numbers |
| SWIFT message parsing | MT103, MT202 |
| ISO 20022 | XML payment message support |

### Business Rules Engine

```python
# Planned: declarative business rules
rules = RuleSet([
    Rule("max_single_payment", lambda tx: tx.amount <= Money.euro(100000)),
    Rule("daily_limit", lambda tx, ctx: ctx.daily_total + tx.amount <= Money.euro(500000)),
    Rule("sanctioned_countries", lambda tx: tx.beneficiary.country not in SANCTIONED),
])

gate = Gate(policy, rules)
```

---

## v3.0 — Cross-System Reconciliation (Q4 2025)

### The Problem

Multiple systems calculate the same financial values:
- ERP system
- Banking middleware
- Accounting software
- AI-assisted forecasting

They must agree to the cent. But they use different:
- Rounding rules
- Calculation order
- Data sources

### The Solution

```python
# Planned: reconciliation framework
from money.reconciliation import Reconciler, Source

reconciler = Reconciler(
    sources=[
        Source("erp", erp_adapter),
        Source("bank", bank_adapter),
        Source("accounting", accounting_adapter),
    ],
    tolerance=Money.euro_cents(0),  # Zero tolerance
    resolution_strategy="manual",    # or "erp_wins", "latest_wins"
)

result = reconciler.reconcile(
    entity="invoice_12345",
    expected=Money.euro(12345_67)
)

if result.discrepancy:
    # IFX-logged discrepancy for audit
    ledger.append(DiscrepancyTransaction(...))
```

---

## Long-Term Vision (2026+)

### Research Areas

| Area | Description | Status |
|------|-------------|--------|
| Formal verification | Z3/SMT encoding of Money invariants | Research |
| Smart contract bridge | Solidity/Ethereum integration | Exploration |
| Real-time risk | Streaming anomaly detection | Exploration |
| Multi-party computation | Privacy-preserving reconciliation | Research |

### Ecosystem Integration

| System | Integration Type |
|--------|------------------|
| Stripe | Payment primitive mapping |
| Plaid | Account balance integration |
| Xero/QuickBooks | Accounting sync |
| SAP/Oracle | ERP connectors |

---

## Contributing

We welcome contributions in these areas:

1. **New currency support**: Add currencies with proper precision
2. **Payment standards**: SEPA, SWIFT, ISO 20022
3. **IFX policies**: New policy types and evaluation strategies
4. **Documentation**: Examples, tutorials, translations
5. **Testing**: Edge cases, fuzzing, property tests

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Related Projects

| Project | Relationship |
|---------|-------------|
| [IFX-vs-KQR](https://github.com/ambradan/IFX-vs-KQR) | Specification framework |
| [Mission-Critical Framework](https://github.com/ambradan/mission-critical) | Development governance |

---

## License

MIT — Use freely, contribute back.
