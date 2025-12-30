#!/usr/bin/env python3
"""
challenge_solution.py — Arkemis Python Challenge 2026

================================================================================
THE BUG
================================================================================

    >>> 2026.0 / 12 * 12
    2025.9999999999998

This is not a Python bug. It's IEEE 754 floating-point arithmetic working
exactly as designed. The problem is using float for money.

================================================================================
THE FIX (Surface Level)
================================================================================

    from decimal import Decimal
    >>> Decimal('2026') / 12 * 12
    Decimal('2026')

This works. But it's treating the symptom, not the disease.

================================================================================
THE REAL FIX (This Solution)
================================================================================

The disease is: money is not a number.

Money has rules that numbers don't:
- Cannot be negative in some contexts
- Has a currency (EUR ≠ USD)
- Has fixed precision (cents, not infinite decimals)
- Must distribute without loss (€100 ÷ 3 = ?)

This solution provides a Domain Primitive that makes the bug IMPOSSIBLE:

    from money import Money, Currency
    
    budget = Money.euro(2026)
    monthly = budget.distribute(12)
    
    # This is not "probably true". It is PROVEN true.
    assert sum(monthly, Money.zero(Currency.EUR)) == budget

================================================================================
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from money import Money, Currency


def demonstrate_bug():
    """Show the original floating-point bug."""
    print("=" * 60)
    print("THE BUG")
    print("=" * 60)
    print()
    print(">>> 2026.0 / 12 * 12")
    result = 2026.0 / 12 * 12
    print(f"{result}")
    print()
    print(f"Expected: 2026.0")
    print(f"Got:      {result}")
    print(f"Diff:     {2026.0 - result}")
    print()


def demonstrate_solution():
    """Show the Money type solution."""
    print("=" * 60)
    print("THE SOLUTION")
    print("=" * 60)
    print()
    
    # Create budget
    budget = Money.euro(2026)
    print(f"Budget: {budget}")
    print()
    
    # Distribute
    monthly = budget.distribute(12)
    print(f"Monthly allocation ({len(monthly)} parts):")
    for i, m in enumerate(monthly, 1):
        print(f"  Month {i:2d}: {m}")
    print()
    
    # Verify invariant
    total = sum(monthly, Money.zero(Currency.EUR))
    print(f"Sum of parts: {total}")
    print(f"Original:     {budget}")
    print(f"Equal?        {total == budget}")
    print()
    
    # Mathematical proof
    print("Why this ALWAYS works:")
    print()
    print("  Let M = 202600 (cents)")
    print("  Let n = 12")
    print("  base = M // n = 16883")
    print("  remainder = M % n = 4")
    print()
    print("  Distribution:")
    print("    4 parts × 16884 cents = 67536")
    print("    8 parts × 16883 cents = 135064")
    print("    Total = 202600 cents ✓")
    print()


def demonstrate_type_safety():
    """Show type safety features."""
    print("=" * 60)
    print("TYPE SAFETY")
    print("=" * 60)
    print()
    
    eur = Money.euro(100)
    usd = Money.usd(100)
    
    print(f"EUR: {eur}")
    print(f"USD: {usd}")
    print()
    
    # Cannot mix currencies
    print(">>> eur + usd")
    try:
        result = eur + usd
    except TypeError as e:
        print(f"TypeError: {e}")
    print()
    
    # Cannot add float
    print(">>> eur + 50.0")
    try:
        result = eur + 50.0
    except TypeError as e:
        print(f"TypeError: {e}")
    print()


def demonstrate_fiscal_operations():
    """Show VAT and discount operations."""
    print("=" * 60)
    print("FISCAL OPERATIONS")
    print("=" * 60)
    print()
    
    price = Money.euro(100)
    print(f"Net price: {price}")
    print()
    
    # Add VAT
    net, vat, gross = price.add_vat(22)
    print("Add 22% VAT:")
    print(f"  Net:   {net}")
    print(f"  VAT:   {vat}")
    print(f"  Gross: {gross}")
    print(f"  Invariant (net + vat == gross): {net + vat == gross}")
    print()
    
    # Extract VAT
    net2, vat2, gross2 = gross.extract_vat(22)
    print("Extract VAT from gross:")
    print(f"  Net:   {net2}")
    print(f"  VAT:   {vat2}")
    print(f"  Gross: {gross2}")
    print(f"  Invariant: {net2 + vat2 == gross2}")
    print()


def demonstrate_serialization():
    """Show safe serialization."""
    print("=" * 60)
    print("SERIALIZATION")
    print("=" * 60)
    print()
    
    original = Money.euro(2026)
    print(f"Original: {original}")
    print()
    
    # Serialize (always integers, never float)
    data = original.to_dict()
    print(f"Serialized: {data}")
    print()
    
    # Deserialize
    restored = Money.from_dict(data)
    print(f"Restored: {restored}")
    print(f"Equal: {original == restored}")
    print()
    
    print("Note: minor_units is ALWAYS an integer.")
    print("This prevents any floating-point corruption in storage/transmission.")
    print()


def main():
    """Run all demonstrations."""
    demonstrate_bug()
    demonstrate_solution()
    demonstrate_type_safety()
    demonstrate_fiscal_operations()
    demonstrate_serialization()
    
    print("=" * 60)
    print("CONCLUSION")
    print("=" * 60)
    print()
    print("The floating-point bug is not a bug to fix.")
    print("It's a design flaw to prevent.")
    print()
    print("Money is not a float. Money is a domain primitive")
    print("with rules that the type system enforces.")
    print()
    print("When the type makes the bug impossible,")
    print("you don't need to remember to avoid it.")
    print()


if __name__ == "__main__":
    main()
