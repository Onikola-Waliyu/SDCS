import csv
import io
from typing import List
from app.db.models import Transaction

def generate_transactions_csv(transactions: List[Transaction]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["ID", "Business ID", "Recorded By", "Item", "Quantity", "Unit", "Amount", "Customer", "Date"])
    for tx in transactions:
        writer.writerow([
            tx.id,
            tx.business_id,
            tx.recorded_by,
            tx.item,
            tx.quantity,
            tx.unit,
            tx.amount,
            tx.customer or "",
            tx.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])

    return output.getvalue()
