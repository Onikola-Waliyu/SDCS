"""
DB persistence and CSV export tests.
Uses shared SQLite fixtures from conftest.py.
"""
from app.utils.exporter import generate_transactions_csv


def test_db_persistence_and_export(sample_transaction):
    assert sample_transaction.id is not None

    csv_data = generate_transactions_csv([sample_transaction])

    assert "rice" in csv_data
    assert "2348012345678" in csv_data
    assert "200000" in csv_data
    assert "Hilary" in csv_data
