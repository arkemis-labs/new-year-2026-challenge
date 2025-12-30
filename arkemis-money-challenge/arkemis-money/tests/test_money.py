"""
test_money.py — Test suite per Money domain primitive

================================================================================
STRUTTURA DEI TEST
================================================================================

1. UNIT TESTS
   Test deterministici per casi specifici e edge cases.

2. PROPERTY-BASED TESTS (Hypothesis)
   Test che verificano PROPRIETA' che devono valere per QUALSIASI input.
   Hypothesis genera migliaia di casi random per trovare controesempi.
   
   Se un property test passa, abbiamo forte confidenza che la proprietà
   vale universalmente, non solo per i casi che abbiamo pensato.

3. INVARIANT TESTS
   Test che verificano che gli invarianti dichiarati nel codice
   siano effettivamente rispettati.

================================================================================
"""

import pytest
from hypothesis import given, assume, settings, HealthCheck
from hypothesis import strategies as st

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from money import Money, Currency, RoundingMode, Allocation


# ==============================================================================
# TEST HELPERS
# ==============================================================================

# Strategia Hypothesis per generare Money validi
@st.composite
def money_strategy(draw, currency=None, min_value=-10_000_00, max_value=10_000_00):
    """Genera Money random per property testing."""
    if currency is None:
        currency = draw(st.sampled_from([Currency.EUR, Currency.USD, Currency.GBP]))
    minor_units = draw(st.integers(min_value=min_value, max_value=max_value))
    return Money.of_minor(minor_units, currency)


@st.composite  
def positive_money_strategy(draw, currency=None):
    """Genera Money positivi."""
    return draw(money_strategy(currency=currency, min_value=1, max_value=10_000_00))


# ==============================================================================
# UNIT TESTS: Costruttori
# ==============================================================================

class TestConstructors:
    """Test per i costruttori di Money."""
    
    def test_of_creates_from_major_units(self):
        m = Money.of(100, Currency.EUR)
        assert m.minor_units == 10000  # 100 EUR = 10000 cents
    
    def test_of_minor_creates_from_minor_units(self):
        m = Money.of_minor(10000, Currency.EUR)
        assert m.minor_units == 10000
    
    def test_euro_shorthand(self):
        m = Money.euro(100)
        assert m.minor_units == 10000
        assert m.currency == Currency.EUR
    
    def test_from_float_with_default_rounding(self):
        m = Money.from_float(99.99, Currency.EUR)
        assert m.minor_units == 9999
    
    def test_from_float_with_half_up_rounding(self):
        # 99.995 -> 100.00 con HALF_UP
        m = Money.from_float(99.995, Currency.EUR, RoundingMode.HALF_UP)
        assert m.minor_units == 10000
    
    def test_from_float_with_down_rounding(self):
        # 99.999 -> 99.99 con DOWN
        m = Money.from_float(99.999, Currency.EUR, RoundingMode.DOWN)
        assert m.minor_units == 9999
    
    def test_zero_creates_zero_money(self):
        m = Money.zero(Currency.EUR)
        assert m.minor_units == 0
        assert m.is_zero()
    
    def test_jpy_has_no_decimals(self):
        m = Money.of(1000, Currency.JPY)
        assert m.minor_units == 1000  # 1 JPY = 1 minor unit
        assert str(m) == "1000 JPY"
    
    def test_kwd_has_three_decimals(self):
        m = Money.of_minor(1500, Currency.KWD)
        assert str(m) == "1.500 KWD"


# ==============================================================================
# UNIT TESTS: Distribuzione
# ==============================================================================

class TestDistribute:
    """Test per distribute() - il cuore della challenge."""
    
    def test_challenge_case_2026_divided_by_12(self):
        """Il caso specifico della challenge."""
        budget = Money.euro(2026)
        parts = budget.distribute(12)
        
        assert len(parts) == 12
        total = Money.zero(Currency.EUR)
        for p in parts:
            total = total + p
        assert total == budget
    
    def test_equal_distribution(self):
        """Quando divide esattamente."""
        m = Money.euro(120)
        parts = m.distribute(12)
        
        assert all(p.minor_units == 1000 for p in parts)  # 10.00 EUR each
    
    def test_distribution_with_remainder(self):
        """Quando c'è resto."""
        m = Money.euro_cents(100)  # 1.00 EUR
        parts = m.distribute(3)
        
        # 100 / 3 = 33 resto 1
        # Quindi: [34, 33, 33] o simile, somma = 100
        total = sum(p.minor_units for p in parts)
        assert total == 100
    
    def test_distribute_one(self):
        """Distribuzione in 1 parte = se stesso."""
        m = Money.euro(100)
        parts = m.distribute(1)
        
        assert len(parts) == 1
        assert parts[0] == m
    
    def test_distribute_more_parts_than_cents(self):
        """Più parti che centesimi: alcune saranno 0."""
        m = Money.euro_cents(5)  # 0.05 EUR
        parts = m.distribute(10)
        
        non_zero = [p for p in parts if not p.is_zero()]
        zero = [p for p in parts if p.is_zero()]
        
        assert len(non_zero) == 5
        assert len(zero) == 5
        
        total = Money.zero(Currency.EUR)
        for p in parts:
            total = total + p
        assert total == m
    
    def test_distribute_zero(self):
        """Distribuzione di zero."""
        m = Money.zero(Currency.EUR)
        parts = m.distribute(5)
        
        assert all(p.is_zero() for p in parts)
    
    def test_distribute_negative(self):
        """Distribuzione di importo negativo (debito)."""
        m = Money.euro_cents(-100)
        parts = m.distribute(3)
        
        total = Money.zero(Currency.EUR)
        for p in parts:
            total = total + p
        assert total == m
    
    def test_distribute_invalid_n(self):
        """n <= 0 solleva ValueError."""
        m = Money.euro(100)
        
        with pytest.raises(ValueError):
            m.distribute(0)
        
        with pytest.raises(ValueError):
            m.distribute(-1)


class TestDistributeWeighted:
    """Test per distribute_weighted()."""
    
    def test_equal_weights(self):
        """Pesi uguali = distribuzione uguale."""
        m = Money.euro_cents(100)
        parts = m.distribute_weighted([1, 1, 1, 1])
        
        total = Money.zero(Currency.EUR)
        for p in parts:
            total = total + p
        assert total == m
    
    def test_unequal_weights(self):
        """Pesi diversi."""
        m = Money.euro_cents(100)
        # 70% e 30%
        parts = m.distribute_weighted([70, 30])
        
        assert parts[0].minor_units == 70
        assert parts[1].minor_units == 30
    
    def test_weighted_invariant(self):
        """Somma deve essere esatta anche con pesi strani."""
        m = Money.euro(1000)
        parts = m.distribute_weighted([33.33, 33.33, 33.34])
        
        total = Money.zero(Currency.EUR)
        for p in parts:
            total = total + p
        assert total == m


# ==============================================================================
# UNIT TESTS: Operazioni fiscali
# ==============================================================================

class TestVAT:
    """Test per operazioni IVA."""
    
    def test_add_vat_22_percent(self):
        """Aggiunta IVA 22%."""
        net = Money.euro(100)
        net_out, vat, gross = net.add_vat(22)
        
        assert net_out == net
        assert vat == Money.euro(22)
        assert gross == Money.euro(122)
        assert net_out + vat == gross
    
    def test_add_vat_preserves_invariant(self):
        """net + vat == gross sempre."""
        net = Money.euro_cents(9999)  # 99.99 EUR
        net_out, vat, gross = net.add_vat(22)
        
        assert net_out + vat == gross
    
    def test_extract_vat_22_percent(self):
        """Scorporo IVA 22%."""
        gross = Money.euro(122)
        net, vat, gross_out = gross.extract_vat(22)
        
        assert gross_out == gross
        assert net + vat == gross
    
    def test_extract_vat_round_trip(self):
        """add_vat -> extract_vat dovrebbe tornare (circa) al netto originale."""
        original_net = Money.euro(100)
        _, _, gross = original_net.add_vat(22)
        recovered_net, _, _ = gross.extract_vat(22)
        
        assert recovered_net == original_net


class TestDiscount:
    """Test per sconti."""
    
    def test_apply_discount_10_percent(self):
        """Sconto 10%."""
        price = Money.euro(100)
        discount, final = price.apply_discount(10)
        
        assert discount == Money.euro(10)
        assert final == Money.euro(90)
        assert discount + final == price
    
    def test_discount_preserves_invariant(self):
        """sconto + finale == originale."""
        price = Money.euro_cents(9999)
        discount, final = price.apply_discount(15)
        
        assert discount + final == price


# ==============================================================================
# UNIT TESTS: Operazioni aritmetiche
# ==============================================================================

class TestArithmetic:
    """Test per operazioni aritmetiche."""
    
    def test_add_same_currency(self):
        a = Money.euro(100)
        b = Money.euro(50)
        assert a + b == Money.euro(150)
    
    def test_add_different_currency_raises(self):
        a = Money.euro(100)
        b = Money.usd(100)
        
        with pytest.raises(TypeError):
            a + b
    
    def test_add_non_money_raises(self):
        a = Money.euro(100)
        
        with pytest.raises(TypeError):
            a + 100
        
        with pytest.raises(TypeError):
            a + 100.0
    
    def test_subtract(self):
        a = Money.euro(100)
        b = Money.euro(30)
        assert a - b == Money.euro(70)
    
    def test_negate(self):
        a = Money.euro(100)
        assert -a == Money.euro_cents(-10000)
    
    def test_abs(self):
        a = Money.euro_cents(-500)
        assert abs(a) == Money.euro_cents(500)
    
    def test_multiply_by_int(self):
        price = Money.euro(10)
        total = price * 5
        assert total == Money.euro(50)
    
    def test_multiply_by_float_raises(self):
        price = Money.euro(10)
        
        with pytest.raises(TypeError):
            price * 1.5


# ==============================================================================
# UNIT TESTS: Comparazione
# ==============================================================================

class TestComparison:
    """Test per comparazioni."""
    
    def test_equal(self):
        assert Money.euro(100) == Money.euro(100)
        assert Money.euro(100) != Money.euro(99)
    
    def test_equal_different_currency(self):
        # 100 EUR != 100 USD (valute diverse)
        assert Money.euro(100) != Money.usd(100)
    
    def test_less_than(self):
        assert Money.euro(50) < Money.euro(100)
        assert not Money.euro(100) < Money.euro(50)
    
    def test_compare_different_currency_raises(self):
        with pytest.raises(TypeError):
            Money.euro(100) < Money.usd(100)


# ==============================================================================
# UNIT TESTS: Serializzazione
# ==============================================================================

class TestSerialization:
    """Test per serializzazione."""
    
    def test_to_dict(self):
        m = Money.euro_cents(12345)
        d = m.to_dict()
        
        assert d == {"minor_units": 12345, "currency": "EUR"}
    
    def test_from_dict(self):
        d = {"minor_units": 12345, "currency": "EUR"}
        m = Money.from_dict(d)
        
        assert m == Money.euro_cents(12345)
    
    def test_round_trip(self):
        original = Money.euro_cents(99999)
        serialized = original.to_dict()
        recovered = Money.from_dict(serialized)
        
        assert recovered == original


# ==============================================================================
# PROPERTY-BASED TESTS (Hypothesis)
# ==============================================================================

class TestDistributeProperties:
    """
    Property-based tests per distribute().
    
    Questi test verificano che certe PROPRIETA' valgano per QUALSIASI input,
    non solo per casi specifici che abbiamo pensato.
    """
    
    @given(
        money=money_strategy(currency=Currency.EUR, min_value=0, max_value=1_000_000_00),
        n=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=1000, suppress_health_check=[HealthCheck.too_slow])
    def test_distribute_sum_equals_original(self, money: Money, n: int):
        """
        PROPRIETA': Per qualsiasi Money m e n > 0:
            sum(m.distribute(n)) == m
        
        Questo è l'invariante fondamentale.
        """
        parts = money.distribute(n)
        
        total = Money.zero(Currency.EUR)
        for p in parts:
            total = total + p
        
        assert total == money, f"Invariante violato: {money}.distribute({n}) = {parts}, sum = {total}"
    
    @given(
        money=money_strategy(currency=Currency.EUR),
        n=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=500)
    def test_distribute_returns_n_parts(self, money: Money, n: int):
        """
        PROPRIETA': distribute(n) restituisce esattamente n parti.
        """
        parts = money.distribute(n)
        assert len(parts) == n
    
    @given(
        money=positive_money_strategy(currency=Currency.EUR),
        n=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=500)
    def test_distribute_parts_differ_by_at_most_one(self, money: Money, n: int):
        """
        PROPRIETA': Per Money positivi, le parti differiscono al più di 1 minor unit.
        
        Questo verifica che la distribuzione sia "equa".
        """
        parts = money.distribute(n)
        values = [p.minor_units for p in parts]
        
        min_val = min(values)
        max_val = max(values)
        
        assert max_val - min_val <= 1, f"Parti troppo diverse: min={min_val}, max={max_val}"
    
    @given(money=money_strategy(currency=Currency.EUR))
    @settings(max_examples=200)
    def test_distribute_one_equals_self(self, money: Money):
        """
        PROPRIETA': m.distribute(1) == [m]
        """
        parts = money.distribute(1)
        
        assert len(parts) == 1
        assert parts[0] == money


class TestArithmeticProperties:
    """Property-based tests per operazioni aritmetiche."""
    
    @given(
        a=money_strategy(currency=Currency.EUR),
        b=money_strategy(currency=Currency.EUR)
    )
    @settings(max_examples=500)
    def test_addition_commutative(self, a: Money, b: Money):
        """a + b == b + a"""
        assert a + b == b + a
    
    @given(
        a=money_strategy(currency=Currency.EUR),
        b=money_strategy(currency=Currency.EUR),
        c=money_strategy(currency=Currency.EUR)
    )
    @settings(max_examples=500)
    def test_addition_associative(self, a: Money, b: Money, c: Money):
        """(a + b) + c == a + (b + c)"""
        assert (a + b) + c == a + (b + c)
    
    @given(a=money_strategy(currency=Currency.EUR))
    @settings(max_examples=200)
    def test_add_zero_identity(self, a: Money):
        """a + 0 == a"""
        zero = Money.zero(Currency.EUR)
        assert a + zero == a
    
    @given(a=money_strategy(currency=Currency.EUR))
    @settings(max_examples=200)
    def test_add_negative_equals_zero(self, a: Money):
        """a + (-a) == 0"""
        result = a + (-a)
        assert result.is_zero()


class TestFiscalProperties:
    """Property-based tests per operazioni fiscali."""
    
    @given(
        money=positive_money_strategy(currency=Currency.EUR),
        rate=st.floats(min_value=0.01, max_value=100, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=500)
    def test_add_vat_invariant(self, money: Money, rate: float):
        """
        PROPRIETA': Per add_vat, net + vat == gross sempre.
        """
        net, vat, gross = money.add_vat(rate)
        assert net + vat == gross
    
    @given(
        money=positive_money_strategy(currency=Currency.EUR),
        rate=st.floats(min_value=0.01, max_value=100, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=500)
    def test_extract_vat_invariant(self, money: Money, rate: float):
        """
        PROPRIETA': Per extract_vat, net + vat == gross sempre.
        """
        net, vat, gross = money.extract_vat(rate)
        assert net + vat == gross
    
    @given(
        money=positive_money_strategy(currency=Currency.EUR),
        percent=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=500)
    def test_discount_invariant(self, money: Money, percent: float):
        """
        PROPRIETA': Per apply_discount, sconto + finale == originale.
        """
        discount, final = money.apply_discount(percent)
        assert discount + final == money


class TestSerializationProperties:
    """Property-based tests per serializzazione."""
    
    @given(money=money_strategy())
    @settings(max_examples=500)
    def test_serialization_round_trip(self, money: Money):
        """
        PROPRIETA': from_dict(to_dict(m)) == m per ogni Money m.
        """
        recovered = Money.from_dict(money.to_dict())
        assert recovered == money


# ==============================================================================
# EDGE CASE TESTS
# ==============================================================================

class TestEdgeCases:
    """Test per casi limite."""
    
    def test_very_large_amount(self):
        """Importi molto grandi (debito sovrano scale)."""
        # 1 trilione di euro in centesimi
        huge = Money.euro_cents(100_000_000_000_000)
        parts = huge.distribute(1000)
        
        total = Money.zero(Currency.EUR)
        for p in parts:
            total = total + p
        assert total == huge
    
    def test_very_small_amount(self):
        """1 centesimo distribuito in molte parti."""
        tiny = Money.euro_cents(1)
        parts = tiny.distribute(100)
        
        non_zero = [p for p in parts if not p.is_zero()]
        assert len(non_zero) == 1
        
        total = Money.zero(Currency.EUR)
        for p in parts:
            total = total + p
        assert total == tiny
    
    def test_negative_amounts(self):
        """Debiti (importi negativi)."""
        debt = Money.euro_cents(-10000)
        parts = debt.distribute(3)
        
        total = Money.zero(Currency.EUR)
        for p in parts:
            total = total + p
        assert total == debt
    
    def test_btc_eight_decimals(self):
        """Bitcoin con 8 decimali."""
        btc = Money.of_minor(100_000_000, Currency.BTC)  # 1 BTC
        parts = btc.distribute(3)
        
        total = Money.zero(Currency.BTC)
        for p in parts:
            total = total + p
        assert total == btc


# ==============================================================================
# ALLOCATION TESTS
# ==============================================================================

class TestAllocation:
    """Test per Allocation helper."""
    
    def test_allocation_with_fixed_parts(self):
        total = Money.euro(1000)
        
        parts = (
            Allocation(total)
            .fixed(Money.euro(300))
            .fixed(Money.euro(200))
            .finalize()
        )
        
        assert len(parts) == 2
        # Il remainder (500) va all'ultima parte
        assert parts[0] == Money.euro(300)
        assert parts[1] == Money.euro(700)  # 200 + 500 remainder
    
    def test_allocation_exact(self):
        total = Money.euro(500)
        
        parts = (
            Allocation(total)
            .fixed(Money.euro(200))
            .fixed(Money.euro(300))
            .finalize()
        )
        
        result_sum = Money.zero(Currency.EUR)
        for p in parts:
            result_sum = result_sum + p
        assert result_sum == total


# ==============================================================================
# MAIN (per run diretto)
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
