BUDGET_2026 = 2026.0
MONTHS = 12

# Calcolo se BUDGET_2026 è divisibile per MONTHS con il '%'
# e lo sottraggo a BUDGET_2026, se fosse divisibile l'operatore restituirebbe 0
# quindi BUDGET_2026 rimarrebbe invariato, essendo che non lo è come sappiamo
# DIV_MONTH conterrà la differenza con il primo numero antecedente che risulta essere divisibile.
# In questo caso il primo numero antecedente a 2026 è 2016 e pertanto DIV_MONTH varrà 10.
DIV_MONTH = BUDGET_2026 % MONTHS

# Sottraggo DIV_MONTH a BUDGET_2026 in modo da creare una rata a numero intero.
NEW_BUDGET = BUDGET_2026 - DIV_MONTH
monthly_budget = NEW_BUDGET / MONTHS

# Aggiungo DIV_MONTH a total, investendo la differenza calcolata precedentemente
# come una tantum necessaria per iscriversi ai corsi oppure per essere utilizzata
# come boost iniziale in modo da prendere il ritmo negli studi
total = DIV_MONTH + 0.0
for _ in range(MONTHS):
    total += monthly_budget

print("Budget mensile:", monthly_budget)
print("Boost iniziale: ", DIV_MONTH)
print("Somma totale:  ", total)
print("È davvero 2026.0?", total == BUDGET_2026)