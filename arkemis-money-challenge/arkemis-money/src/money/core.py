"""
money.py — Domain Primitive per rappresentazione monetaria

================================================================================
DESIGN PRINCIPLES
================================================================================

1. RAPPRESENTAZIONE INTERNA
   Interi in minor unit (centesimi per EUR, cents per USD, ecc.).
   Mai floating point internamente.

2. TYPE SAFETY
   Operazioni tra valute diverse sollevano TypeError.
   Operazioni con float/int sollevano TypeError (conversione esplicita richiesta).

3. IMMUTABILITA
   Frozen dataclass. Ogni operazione restituisce nuova istanza.
   Nessun side effect, safe per concorrenza.

4. PRECISION VARIABILE
   Ogni valuta ha la sua precisione (EUR=2, JPY=0, KWD=3).
   La precision è parte del tipo, non un parametro runtime.

5. ROUNDING ESPLICITO
   Nessun arrotondamento implicito. Quando serve, il chiamante sceglie la strategia.

6. INVARIANTI VERIFICABILI
   distribute(n) garantisce sum(parts) == original (dimostrazione formale).
   Operazioni fiscali (VAT, discount) preservano tracciabilità.

================================================================================
DOMAIN PRIMITIVE PATTERN
================================================================================

Questo modulo implementa il pattern "Domain Primitive" (anche noto come "Value Object"
nel DDD o "Tiny Types" in alcuni contesti).

Principio: quando un concetto del dominio ha vincoli o regole, lo si incapsula
in un tipo che rende IMPOSSIBILE violarli.

Esempi di Domain Primitives:
- Money (questo modulo): importo + valuta, operazioni type-safe
- Email: stringa che rispetta RFC 5322
- Percentage: valore 0-100 o 0-1, con semantica chiara
- Quantity: non negativa, unità di misura

Il vantaggio rispetto a usare tipi primitivi (float, str, int):
- Errori di dominio diventano errori di tipo (compile-time o early runtime)
- Impossibile passare EUR dove servono USD
- Impossibile confondere prezzo lordo e netto
- Self-documenting code

================================================================================
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Callable
import math


# ==============================================================================
# CURRENCY DEFINITIONS (ISO 4217)
# ==============================================================================

class Currency(Enum):
    """
    Valute supportate con relative precision (decimali della minor unit).
    
    ISO 4217 definisce:
    - Codice alfabetico (EUR, USD, ...)
    - Codice numerico (978, 840, ...)
    - Minor unit (numero di decimali)
    
    Qui usiamo solo codice e minor unit.
    """
    EUR = ("EUR", 2)   # Euro: 1 EUR = 100 cents
    USD = ("USD", 2)   # US Dollar: 1 USD = 100 cents
    GBP = ("GBP", 2)   # British Pound: 1 GBP = 100 pence
    JPY = ("JPY", 0)   # Japanese Yen: no minor unit
    KWD = ("KWD", 3)   # Kuwaiti Dinar: 1 KWD = 1000 fils
    BTC = ("BTC", 8)   # Bitcoin: 1 BTC = 100,000,000 satoshi
    
    def __init__(self, code: str, decimals: int):
        self._code = code
        self._decimals = decimals
    
    @property
    def code(self) -> str:
        return self._code
    
    @property
    def decimals(self) -> int:
        return self._decimals
    
    @property
    def multiplier(self) -> int:
        """Fattore di conversione major -> minor unit."""
        return 10 ** self._decimals


# ==============================================================================
# ROUNDING STRATEGIES
# ==============================================================================

class RoundingMode(Enum):
    """
    Strategie di arrotondamento.
    
    La scelta della strategia ha impatto reale:
    - HALF_UP: classico arrotondamento commerciale (0.5 -> 1)
    - HALF_EVEN: banker's rounding, minimizza bias statistico
    - DOWN: sempre verso zero (truncation)
    - UP: sempre via da zero
    - HALF_DOWN: 0.5 -> 0
    
    In contesti finanziari, spesso la normativa impone una strategia specifica.
    """
    HALF_UP = "half_up"
    HALF_EVEN = "half_even"  # Python default, IEEE 754 default
    DOWN = "down"
    UP = "up"
    HALF_DOWN = "half_down"


def _apply_rounding(value: float, mode: RoundingMode) -> int:
    """Applica la strategia di arrotondamento e restituisce intero."""
    
    def _half_up(v: float) -> int:
        return math.floor(v + 0.5)
    
    def _half_even(v: float) -> int:
        return round(v)
    
    def _down(v: float) -> int:
        return int(v) if v >= 0 else math.ceil(v)
    
    def _up(v: float) -> int:
        return math.ceil(v) if v >= 0 else int(v)
    
    def _half_down(v: float) -> int:
        return math.ceil(v - 0.5) if v >= 0 else math.floor(v + 0.5)
    
    strategies = {
        RoundingMode.HALF_UP: _half_up,
        RoundingMode.HALF_EVEN: _half_even,
        RoundingMode.DOWN: _down,
        RoundingMode.UP: _up,
        RoundingMode.HALF_DOWN: _half_down,
    }
    
    strategy = strategies.get(mode)
    if strategy is None:
        raise ValueError(f"Unknown rounding mode: {mode}")
    
    return strategy(value)


# ==============================================================================
# MONEY CLASS
# ==============================================================================

@dataclass(frozen=True, slots=True, order=False)
class Money:
    """
    Domain Primitive per importi monetari.
    
    INVARIANTI:
    1. _minor_units è sempre int (nessun floating point)
    2. _currency è sempre Currency (type-safe)
    3. Operazioni tra valute diverse sollevano TypeError
    4. distribute(n) garantisce sum(parts) == self
    
    USAGE:
        budget = Money.euro(2026)
        monthly = budget.distribute(12)
        # sum(monthly) == budget (guaranteed by design)
    
    SERIALIZATION:
        Per persistenza/API, usare to_dict() e from_dict().
        Il formato è: {"minor_units": int, "currency": str}
        MAI serializzare come float.
    """
    _minor_units: int
    _currency: Currency
    
    # -------------------------------------------------------------------------
    # Costruttori
    # -------------------------------------------------------------------------
    
    @classmethod
    def of(cls, major_units: int, currency: Currency) -> Money:
        """
        Costruttore generico da major units (euro, dollari, ecc.).
        Solo per valori interi. Per decimali, usare of_minor() o from_float().
        """
        return cls(
            _minor_units=major_units * currency.multiplier,
            _currency=currency
        )
    
    @classmethod
    def of_minor(cls, minor_units: int, currency: Currency) -> Money:
        """
        Costruttore da minor units (centesimi, cents, ecc.).
        Nessuna conversione, massima precisione.
        """
        return cls(_minor_units=minor_units, _currency=currency)
    
    @classmethod
    def from_float(
        cls, 
        value: float, 
        currency: Currency,
        rounding: RoundingMode = RoundingMode.HALF_EVEN
    ) -> Money:
        """
        Costruttore da float.
        
        ATTENZIONE: L'arrotondamento avviene QUI, una sola volta.
        Da questo punto in poi, tutto è intero.
        
        Questo metodo esiste per compatibilità con sistemi legacy o input utente.
        In un sistema greenfield, preferire of() o of_minor().
        """
        minor_float = value * currency.multiplier
        minor_int = _apply_rounding(minor_float, rounding)
        return cls(_minor_units=minor_int, _currency=currency)
    
    @classmethod
    def zero(cls, currency: Currency) -> Money:
        """Zero per una data valuta. Utile come valore iniziale per sum()."""
        return cls(_minor_units=0, _currency=currency)
    
    # Shorthand per valute comuni
    @classmethod
    def euro(cls, value: int) -> Money:
        return cls.of(value, Currency.EUR)
    
    @classmethod
    def euro_cents(cls, cents: int) -> Money:
        return cls.of_minor(cents, Currency.EUR)
    
    @classmethod
    def usd(cls, value: int) -> Money:
        return cls.of(value, Currency.USD)
    
    @classmethod
    def usd_cents(cls, cents: int) -> Money:
        return cls.of_minor(cents, Currency.USD)
    
    # -------------------------------------------------------------------------
    # Distribuzione (core della challenge)
    # -------------------------------------------------------------------------
    
    # Maximum parts for distribution (DoS protection)
    MAX_DISTRIBUTION_PARTS: int = 10_000
    
    def distribute(self, n: int) -> list[Money]:
        """
        Distribuisce l'importo in n parti con somma ESATTA.
        
        Algoritmo: Largest Remainder Method.
        Invariante: sum(distribute(n)) == self (vedi docs/PROOF.md)
        
        Args:
            n: Numero di parti (1 <= n <= MAX_DISTRIBUTION_PARTS)
        
        Returns:
            Lista di n Money la cui somma è esattamente self
        
        Raises:
            ValueError: se n <= 0 o n > MAX_DISTRIBUTION_PARTS
        """
        if n <= 0:
            raise ValueError(f"n deve essere > 0, ricevuto: {n}")
        if n > self.MAX_DISTRIBUTION_PARTS:
            raise ValueError(f"n supera il limite di {self.MAX_DISTRIBUTION_PARTS}")
        
        base = self._minor_units // n
        remainder = self._minor_units % n
        
        return [
            Money.of_minor(base + (1 if i < remainder else 0), self._currency)
            for i in range(n)
        ]
    
    def distribute_weighted(
        self, 
        weights: list[float],
        rounding: RoundingMode = RoundingMode.HALF_EVEN
    ) -> list[Money]:
        """
        Distribuisce l'importo proporzionalmente ai pesi dati.
        
        Utile per: quote societarie, split proporzionali, ecc.
        
        INVARIANTE: sum(result) == self (garantito)
        
        ALGORITMO:
        1. Calcola importi proporzionali (float)
        2. Arrotonda ciascuno
        3. Calcola differenza tra somma arrotondata e totale
        4. Aggiusta la parte più grande per compensare
        
        NOTA: Esistono algoritmi più sofisticati (Hare-Niemeyer, D'Hondt)
        per distribuzioni più "eque". Questo è semplice e corretto.
        """
        if not weights:
            raise ValueError("weights non può essere vuoto")
        if len(weights) > self.MAX_DISTRIBUTION_PARTS:
            raise ValueError(f"weights supera il limite di {self.MAX_DISTRIBUTION_PARTS}")
        if any(w < 0 for w in weights):
            raise ValueError("weights non può contenere valori negativi")
        
        total_weight = sum(weights)
        if total_weight == 0:
            raise ValueError("somma dei weights non può essere 0")
        
        # Calcola proporzioni
        proportions = [w / total_weight for w in weights]
        
        # Calcola importi arrotondati
        raw_amounts = [self._minor_units * p for p in proportions]
        rounded = [_apply_rounding(a, rounding) for a in raw_amounts]
        
        # Calcola differenza
        diff = self._minor_units - sum(rounded)
        
        # Aggiusta: aggiungi/togli la differenza alla parte con peso maggiore
        if diff != 0:
            max_idx = weights.index(max(weights))
            rounded[max_idx] += diff
        
        return [Money.of_minor(r, self._currency) for r in rounded]
    
    # -------------------------------------------------------------------------
    # Operazioni fiscali
    # -------------------------------------------------------------------------
    
    def add_vat(
        self, 
        rate_percent: float,
        rounding: RoundingMode = RoundingMode.HALF_EVEN
    ) -> tuple[Money, Money, Money]:
        """
        Calcola importo + IVA.
        
        Args:
            rate_percent: aliquota in percentuale (es. 22 per 22%)
            rounding: strategia di arrotondamento per l'IVA
        
        Returns:
            (netto, iva, lordo) come tuple di Money
        
        INVARIANTE: netto + iva == lordo (garantito)
        
        NOTA: In alcuni contesti normativi, l'arrotondamento IVA
        ha regole specifiche. Verificare la normativa applicabile.
        """
        rate_decimal = rate_percent / 100
        vat_float = self._minor_units * rate_decimal
        vat_minor = _apply_rounding(vat_float, rounding)
        
        net = self
        vat = Money.of_minor(vat_minor, self._currency)
        gross = Money.of_minor(self._minor_units + vat_minor, self._currency)
        
        return (net, vat, gross)
    
    def extract_vat(
        self,
        rate_percent: float,
        rounding: RoundingMode = RoundingMode.HALF_EVEN
    ) -> tuple[Money, Money, Money]:
        """
        Estrae IVA da un importo lordo (scorporo).
        
        Formula: netto = lordo / (1 + rate)
                 iva = lordo - netto
        
        Returns:
            (netto, iva, lordo) come tuple di Money
        
        INVARIANTE: netto + iva == lordo (garantito, lordo è self)
        """
        rate_decimal = rate_percent / 100
        net_float = self._minor_units / (1 + rate_decimal)
        net_minor = _apply_rounding(net_float, rounding)
        
        vat_minor = self._minor_units - net_minor  # Garantisce invariante
        
        net = Money.of_minor(net_minor, self._currency)
        vat = Money.of_minor(vat_minor, self._currency)
        gross = self
        
        return (net, vat, gross)
    
    def apply_discount(
        self,
        percent: float,
        rounding: RoundingMode = RoundingMode.HALF_EVEN
    ) -> tuple[Money, Money]:
        """
        Applica sconto percentuale.
        
        Returns:
            (sconto, prezzo_scontato) come tuple di Money
        
        INVARIANTE: sconto + prezzo_scontato == self
        """
        discount_float = self._minor_units * (percent / 100)
        discount_minor = _apply_rounding(discount_float, rounding)
        
        discount = Money.of_minor(discount_minor, self._currency)
        discounted = Money.of_minor(self._minor_units - discount_minor, self._currency)
        
        return (discount, discounted)
    
    # -------------------------------------------------------------------------
    # Operazioni aritmetiche (type-safe)
    # -------------------------------------------------------------------------
    
    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            raise TypeError(
                f"Operazione non permessa: Money + {type(other).__name__}. "
                f"Usa Money.of() o Money.from_float() per convertire."
            )
        if self._currency != other._currency:
            raise TypeError(
                f"Valute diverse: {self._currency.code} + {other._currency.code}. "
                f"Converti esplicitamente prima di sommare."
            )
        return Money.of_minor(
            self._minor_units + other._minor_units,
            self._currency
        )
    
    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            raise TypeError(
                f"Operazione non permessa: Money - {type(other).__name__}."
            )
        if self._currency != other._currency:
            raise TypeError(
                f"Valute diverse: {self._currency.code} - {other._currency.code}."
            )
        return Money.of_minor(
            self._minor_units - other._minor_units,
            self._currency
        )
    
    def __neg__(self) -> Money:
        return Money.of_minor(-self._minor_units, self._currency)
    
    def __abs__(self) -> Money:
        return Money.of_minor(abs(self._minor_units), self._currency)
    
    def __mul__(self, factor: int) -> Money:
        """
        Moltiplicazione per intero (quantità).
        
        Esempio: prezzo_unitario * quantita
        
        Per moltiplicare per percentuale, usare apply_percentage().
        """
        if not isinstance(factor, int):
            raise TypeError(
                f"Money può essere moltiplicato solo per int (quantità), "
                f"non {type(factor).__name__}. Per percentuali, usa apply_percentage()."
            )
        return Money.of_minor(self._minor_units * factor, self._currency)
    
    def __rmul__(self, factor: int) -> Money:
        return self.__mul__(factor)
    
    def apply_percentage(
        self,
        percent: float,
        rounding: RoundingMode = RoundingMode.HALF_EVEN
    ) -> Money:
        """
        Moltiplica per una percentuale.
        
        Esempio: importo.apply_percentage(15) per calcolare il 15%.
        """
        result_float = self._minor_units * (percent / 100)
        result_minor = _apply_rounding(result_float, rounding)
        return Money.of_minor(result_minor, self._currency)
    
    # -------------------------------------------------------------------------
    # Comparazione
    # -------------------------------------------------------------------------
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Money):
            return (
                self._minor_units == other._minor_units 
                and self._currency == other._currency
            )
        return NotImplemented
    
    def __lt__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self._minor_units < other._minor_units
    
    def __le__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self._minor_units <= other._minor_units
    
    def __gt__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self._minor_units > other._minor_units
    
    def __ge__(self, other: Money) -> bool:
        self._check_same_currency(other)
        return self._minor_units >= other._minor_units
    
    def _check_same_currency(self, other: Money) -> None:
        if not isinstance(other, Money):
            raise TypeError(f"Impossibile comparare Money con {type(other).__name__}")
        if self._currency != other._currency:
            raise TypeError(
                f"Impossibile comparare valute diverse: "
                f"{self._currency.code} vs {other._currency.code}"
            )
    
    # -------------------------------------------------------------------------
    # Proprietà e output
    # -------------------------------------------------------------------------
    
    @property
    def minor_units(self) -> int:
        """Valore in minor units (centesimi, ecc.). Per persistenza/calcoli."""
        return self._minor_units
    
    @property
    def currency(self) -> Currency:
        """Valuta."""
        return self._currency
    
    @property
    def major_units(self) -> float:
        """
        Valore in major units (euro, dollari, ecc.).
        
        ATTENZIONE: restituisce float, usare SOLO per display.
        Non usare per calcoli.
        """
        return self._minor_units / self._currency.multiplier
    
    def is_positive(self) -> bool:
        return self._minor_units > 0
    
    def is_negative(self) -> bool:
        return self._minor_units < 0
    
    def is_zero(self) -> bool:
        return self._minor_units == 0
    
    def __repr__(self) -> str:
        sign = "-" if self._minor_units < 0 else ""
        abs_minor = abs(self._minor_units)
        decimals = self._currency.decimals
        
        if decimals == 0:
            return f"{sign}{abs_minor} {self._currency.code}"
        
        major = abs_minor // self._currency.multiplier
        minor = abs_minor % self._currency.multiplier
        
        return f"{sign}{major}.{minor:0{decimals}d} {self._currency.code}"
    
    def __str__(self) -> str:
        return self.__repr__()
    
    def __hash__(self) -> int:
        return hash((self._minor_units, self._currency))
    
    # -------------------------------------------------------------------------
    # Serializzazione
    # -------------------------------------------------------------------------
    
    def to_dict(self) -> dict:
        """
        Serializza per persistenza/API.
        
        Formato: {"minor_units": int, "currency": str}
        
        NOTA: MAI serializzare come float. Sempre minor_units come int.
        """
        return {
            "minor_units": self._minor_units,
            "currency": self._currency.code
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Money:
        """
        Deserializza da dict.
        
        Accetta formato: {"minor_units": int, "currency": str}
        """
        currency = Currency[data["currency"]]
        return cls.of_minor(data["minor_units"], currency)


# ==============================================================================
# ALLOCATION (distribuzione complessa)
# ==============================================================================

class Allocation:
    """
    Helper per distribuzioni complesse.
    
    Quando serve distribuire un importo secondo regole specifiche:
    - Quote fisse + variabili
    - Minimum/maximum per parte
    - Priorità
    
    INVARIANTE: sum(allocate()) == original (sempre)
    """
    
    def __init__(self, total: Money):
        self._total = total
        self._allocated = Money.zero(total.currency)
        self._parts: list[Money] = []
    
    def fixed(self, amount: Money) -> Allocation:
        """Alloca una quota fissa."""
        if amount.currency != self._total.currency:
            raise TypeError("Valuta diversa dal totale")
        self._parts.append(amount)
        self._allocated = self._allocated + amount
        return self
    
    def remainder(self) -> Money:
        """Restituisce il residuo non ancora allocato."""
        return self._total - self._allocated
    
    def finalize(self) -> list[Money]:
        """
        Finalizza l'allocazione.
        
        Se c'è residuo, lo aggiunge all'ultima parte.
        
        Returns:
            Lista di parti la cui somma == totale originale
        """
        remainder = self.remainder()
        if not remainder.is_zero():
            if self._parts:
                # Aggiunge il resto all'ultima parte
                self._parts[-1] = self._parts[-1] + remainder
            else:
                self._parts.append(remainder)
        return self._parts.copy()
