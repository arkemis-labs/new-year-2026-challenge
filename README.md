# 🧩 Arkemis Python Challenge 2026

<img width="2908" height="913" alt="Arkemis - Cover" src="https://github.com/user-attachments/assets/706e2095-6789-4de3-a5a0-9ef76df773ca" />

## Mancano 24 ore al 2026: sistema questo bug prima dell’anno nuovo

Hai deciso che nel 2026 investirai esattamente 2026€ in te stesso: corsi, conferenze, strumenti, formazione (gran parte con Arkemis 😜 ).

Per prepararti, scrivi uno script Python per dividere il budget in 12 mesi.  
Il codice gira, ma il risultato finale **non torna**.

Ed è qui che inizia la challenge.

---

## La challenge

Questo è il codice di partenza:

```python
BUDGET_2026 = 2026.0
MONTHS = 12

monthly_budget = BUDGET_2026 / MONTHS

total = 0.0
for _ in range(MONTHS):
    total += monthly_budget

print("Budget mensile:", monthly_budget)
print("Somma totale:  ", total)
print("È davvero 2026.0?", total == BUDGET_2026)
```

Output:
```python
Budget mensile: 168.83333333333334
Somma totale:   2025.9999999999998
È davvero 2026.0? False
```

❓Domanda
Perché non ottieni mai esattamente 2026 quando sommi il budget mensile?

Bene, la tua missione nelle prossime 24 ore sarà:
1. Capire perché il totale non è esattamente 2026.0,
2. Proporre una soluzione robusta (non usare round() a caso),
3. Spiegare nei commenti cosa hai fatto e come hai gestito l'arrotondamento in Python.

## Come partecipare

Le soluzioni si inviano esclusivamente tramite Pull Request.
1.	Forka il repository
2.	Crea un branch:
```bash
git checkout -b fix/your-name
```

3.	Implementa la tua soluzione
Apri una Pull Request verso main

Nel testo della PR spiega:
- perché il codice originale fallisce
- quale approccio hai scelto
- come gestisci l’arrotondamento
- perché la soluzione è robusta
- output finale o esempio di esecuzione

## Valutazione

Tutte le Pull Request verranno reviewate da Arkemis.
La correttezza della soluzione verrà confermata con un commento direttamente nella PR.

Il vincitore verrà annunciato il 2 gennaio su LinkedIn.

I criteri di valutazione sono:
- correttezza tecnica
- chiarezza della spiegazione
- solidità dell’approccio
- qualità del codice

## Deadline

🕛 31 dicembre – ore 23:59 (CET)

Se partecipi:
- lascia una ⭐ al repository
- Condividi la tua PR nei commenti del post su LinkedIn
• usa gli hashtag: #arkemis #challenge #python #developers #2026

Buon hacking e buon 2026 🚀

