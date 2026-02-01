#!/usr/bin/env python3
"""
Test suite for PDF parser v3.
Run: python test_pdf_parser.py
"""

import sys
sys.path.insert(0, 'app/backend')

from pdf_parser_v3 import parse_reservation_pdf_v3
from datetime import date


def test_parse_sample_pdf():
    """Test parsing of sample PDF."""
    print("="*80)
    print("TEST: Parse Sample PDF")
    print("="*80)
    
    with open("77c7e340-62f8-4a95-aa5f-3af26d52b7e1.pdf", "rb") as f:
        pdf_bytes = f.read()
    
    result = parse_reservation_pdf_v3(
        pdf_bytes=pdf_bytes,
        service_date=date(2026, 1, 31),
        service_label="lunch",
        debug=False
    )
    
    reservations = result["reservations"]
    stats = result["stats"]
    
    # Assertions
    assert len(reservations) > 0, "Should parse at least 1 reservation"
    assert len(reservations) >= 18, f"Should parse at least 18 reservations, got {len(reservations)}"
    
    # Check first reservation structure
    first = reservations[0]
    assert "id" in first, "Reservation should have id"
    assert "client_name" in first, "Reservation should have client_name"
    assert "pax" in first, "Reservation should have pax"
    assert "arrival_time" in first, "Reservation should have arrival_time"
    assert "service_date" in first, "Reservation should have service_date"
    
    # Check data quality
    assert len(first["client_name"]) >= 2, "Client name should be at least 2 chars"
    assert 1 <= first["pax"] <= 30, "Pax should be between 1 and 30"
    assert ":" in first["arrival_time"], "Arrival time should be in HH:MM format"
    
    print(f"✓ Parsed {len(reservations)} reservations")
    print(f"✓ First reservation: {first['client_name']} @ {first['arrival_time']} ({first['pax']} pax)")
    print(f"✓ All structure checks passed")
    return True


def test_expected_names():
    """Test that expected names are extracted."""
    print("\n" + "="*80)
    print("TEST: Expected Names")
    print("="*80)
    
    with open("77c7e340-62f8-4a95-aa5f-3af26d52b7e1.pdf", "rb") as f:
        pdf_bytes = f.read()
    
    result = parse_reservation_pdf_v3(
        pdf_bytes=pdf_bytes,
        service_date=date(2026, 1, 31),
        service_label="lunch",
        debug=False
    )
    
    reservations = result["reservations"]
    names = [r["client_name"] for r in reservations]
    
    # Expected names from manual inspection
    expected_names = [
        "DE LERA Sara",
        "SCHOOFS Sarah",
        "TROTTA Lina",
        "JACKSON Rebecca",
    ]
    
    for expected in expected_names:
        assert expected in names, f"Expected name '{expected}' not found in parsed names"
        print(f"✓ Found: {expected}")
    
    # Check no garbage names
    garbage_patterns = ["17", "8657", "3946", "0061"]
    for name in names:
        for garbage in garbage_patterns:
            assert name != garbage, f"Found garbage name: {garbage}"
    
    print(f"✓ No garbage names found")
    return True


def test_stats():
    """Test statistics are correct."""
    print("\n" + "="*80)
    print("TEST: Statistics")
    print("="*80)
    
    with open("77c7e340-62f8-4a95-aa5f-3af26d52b7e1.pdf", "rb") as f:
        pdf_bytes = f.read()
    
    result = parse_reservation_pdf_v3(
        pdf_bytes=pdf_bytes,
        service_date=date(2026, 1, 31),
        service_label="lunch",
        debug=False
    )
    
    stats = result["stats"]
    reservations = result["reservations"]
    
    assert stats["total_parsed"] == len(reservations), "Stats should match actual count"
    assert stats["service_date"] == "2026-01-31", "Service date should match"
    assert stats["service_label"] == "lunch", "Service label should match"
    
    print(f"✓ total_parsed: {stats['total_parsed']}")
    print(f"✓ service_date: {stats['service_date']}")
    print(f"✓ service_label: {stats['service_label']}")
    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*80)
    print("PDF PARSER V3 - TEST SUITE")
    print("="*80 + "\n")
    
    tests = [
        ("Parse Sample PDF", test_parse_sample_pdf),
        ("Expected Names", test_expected_names),
        ("Statistics", test_stats),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ TEST FAILED: {name}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ TEST ERROR: {name}")
            print(f"  Exception: {e}")
            failed += 1
    
    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n✗ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
