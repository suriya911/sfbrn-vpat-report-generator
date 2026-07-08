from vpat_reviewer.parsing.metadata import extract_meta


def test_product_name_and_version_split():
    meta = extract_meta("Name of Product/Version: TestApp 2.1")
    assert meta["product_name"] == "TestApp"
    assert meta["product_version"] == "2.1"


def test_version_prefix_form():
    meta = extract_meta("Product Name: CoolApp Version 3.4.5")
    assert meta["product_name"] == "CoolApp"
    assert meta["product_version"] == "3.4.5"


def test_windows_10_not_split_as_version():
    # A bare integer must not be treated as a version (needs a decimal point).
    meta = extract_meta("Product: Windows 10")
    assert meta["product_name"] == "Windows 10"
    assert "product_version" not in meta


def test_report_date_and_vendor():
    meta = extract_meta("Report Date: March 5, 2023\nVendor: Acme Corporation")
    assert meta["vendor_report_date_raw"] == "March 5, 2023"
    assert meta["vendor_name"] == "Acme Corporation"


def test_description_stops_at_next_key():  # v9 FIX E
    text = (
        "Product Description: A collaborative statistics package used by many teams.\n"
        "Date: August 2020\n"
    )
    meta = extract_meta(text)
    assert "collaborative statistics package" in meta["product_description"]
    assert "August 2020" not in meta["product_description"]


def test_known_vendor_scanned_in_header():
    meta = extract_meta("Instructure Canvas VPAT\n" + "x" * 50)
    assert meta["vendor_name"] == "Instructure"


def test_email_contact_fallback():
    meta = extract_meta("Questions? reach a11y@vendor.com anytime.")
    assert meta["vendor_contact"] == "a11y@vendor.com"
