BUDGET_2026 = 2026.0
MONTHS = 12

monthly_budget = BUDGET_2026 / MONTHS

total = 0.0
for _ in range(MONTHS):
    total += monthly_budget

print("Budget mensile:", monthly_budget)
print("Somma totale:  ", total)
print("È davvero 2026.0?", total == BUDGET_2026)
