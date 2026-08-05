"""Import the curated pharmacy catalog (images in ../medicines/) into the demo pharmacy.

Run from backend/:
    .venv/bin/python import_pharmacy_catalog.py
"""
import os
import shutil
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

from services.models import Medicine  # noqa: E402

IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "medicines")

# filename -> (name, description, price UGX, stock)
CATALOG = {
    "0718e3127bbfbb57dede673e1776d9e6.jpg": (
        "Multivitamin Tablets (30 tablets)",
        "Daily multivitamin with vitamins A, C, D, E and zinc for immune support and general wellness.",
        18000, 240,
    ),
    "105b6c9a3fb4d4d55373d62b8b5e4cf3.jpg": (
        "Calcium + Vitamin D3 Tablets (60 tablets)",
        "Bone-strength supplement combining calcium carbonate with vitamin D3 for better absorption.",
        22000, 180,
    ),
    "1d92b2a7d2e52b371664ac962a52fd0c.jpg": (
        "Amoxicillin 500 mg Capsules (21 capsules)",
        "Broad-spectrum penicillin antibiotic for bacterial infections of the ear, throat, chest and urinary tract.",
        15000, 150,
    ),
    "2de383df7a56dfe2484070759d46c971.jpg": (
        "Digital Infrared Forehead Thermometer",
        "Non-contact fever screening with instant reading, fever alarm and memory recall. Batteries included.",
        85000, 45,
    ),
    "33f16cd61b6632eb4f4d0a6e93c446c3.jpg": (
        "Ibuprofen 400 mg Tablets (20 tablets)",
        "Anti-inflammatory pain relief for headaches, dental pain, muscle aches and period pain.",
        6000, 300,
    ),
    "384ec558c01ac12650f5f160158c6d57.jpg": (
        "Family First Aid Kit (42 pieces)",
        "Complete home and travel kit with bandages, antiseptic, gauze, scissors, gloves and emergency guide.",
        65000, 60,
    ),
    "43ad4ff646a7af00329d5bf91dc6268a.jpg": (
        "Disposable Syringe 10 ml (Pack of 10)",
        "Sterile, single-use Luer-lock syringes with needles, individually wrapped.",
        8000, 400,
    ),
    "5a430ef0cc4c59bcdc73c9eb4f284518.jpg": (
        "Omeprazole 20 mg Capsules (28 capsules)",
        "Proton-pump inhibitor for heartburn, acid reflux and stomach-ulcer treatment.",
        12000, 200,
    ),
    "5f626b0e93aa324d4d0e21dce87be997.jpg": (
        "Digital Clinical Thermometer",
        "Fast, accurate oral/underarm thermometer with flexible tip, waterproof body and beeper.",
        25000, 90,
    ),
    "7824e0353b1ea778a539764c61636875.jpg": (
        "Cetirizine 10 mg Tablets (30 tablets)",
        "Non-drowsy antihistamine for allergies, hay fever, itching and skin reactions.",
        7000, 260,
    ),
    "7b9d2eb62859bde13fd5d644d20d1b4c.jpg": (
        "Fingertip Pulse Oximeter",
        "SpO2 and pulse-rate monitoring with bright OLED display. Suitable for home and clinical use.",
        95000, 40,
    ),
    "8a07d5ccf1d8acc4eb54980a8de0996d.jpg": (
        "IV Cannula 20G (Pack of 5)",
        "Sterile intravenous cannulas with injection port and wings for secure placement.",
        15000, 180,
    ),
    "8d73b89b3fa5050585fb55a30e632bb9.jpg": (
        "Iron + Folic Acid Capsules (30 capsules)",
        "Ferrous fumarate with folic acid for anaemia prevention, including in pregnancy.",
        10000, 220,
    ),
    "c147199a38b796f7920f396161c368af.jpg": (
        "Vitamin B-Complex Tablets (60 tablets)",
        "Full B-vitamin spectrum for energy metabolism, nerve health and fatigue reduction.",
        16000, 170,
    ),
    "c19b35e276eaf20fcc15a91e29e98731.jpg": (
        "Paracetamol 500 mg (50 tablets)",
        "Value pack fever and pain relief. Suitable for adults and children over 12 years.",
        6500, 350,
    ),
    "d2e2ad9ac95ae273aef0ad479bc217e5.jpg": (
        "Azithromycin 250 mg Tablets (6 tablets)",
        "Macrolide antibiotic for respiratory, skin and sexually transmitted infections.",
        14000, 130,
    ),
    "d49888915bb1fc7686316292c17da054.jpg": (
        "Antacid Tablets, Mint (48 tablets)",
        "Fast relief from heartburn, indigestion and acid stomach with magnesium/aluminium hydroxide.",
        5500, 280,
    ),
    "dd2e1f8a8313dfe7114da398485b786a.jpg": (
        "Metronidazole 400 mg Tablets (21 tablets)",
        "Antibiotic and antiprotozoal for dental, abdominal and gynaecological infections.",
        9000, 160,
    ),
    "e008e3753f29dc77d6e729686f6420af.jpg": (
        "Doxycycline 100 mg Capsules (14 capsules)",
        "Tetracycline antibiotic for malaria prophylaxis, respiratory and skin infections.",
        11000, 140,
    ),
    "eb659e336fc380c675ad8e6a88218982.jpg": (
        "Multimineral Softgel Capsules (30 softgels)",
        "Magnesium, zinc, selenium and trace minerals in easy-to-swallow softgels.",
        20000, 110,
    ),
    "f647dca09755ceecf84fc3422a33f162.jpg": (
        "Basal Digital Thermometer",
        "High-precision thermometer for fertility and basal body temperature tracking.",
        30000, 55,
    ),
    "f7671186b6cd3ceaa3d06d85f1f0814c.jpg": (
        "Disposable Syringe 2.5 ml (Pack of 20)",
        "Sterile single-use syringes with fine-gauge needles for vaccinations and injections.",
        10000, 500,
    ),
    "f97fd02b3ad111794b6f7cc0e67fca8a.jpg": (
        "Omega-3 Fish Oil Softgels (60 softgels)",
        "1000 mg fish oil with EPA/DHA for heart, brain and joint health.",
        28000, 120,
    ),
}


def main():
    User = get_user_model()
    pharmacy = User.objects.get(email="pharmacy@healthpilot.test")
    media_target = os.path.join(settings.MEDIA_ROOT, "medicines")
    os.makedirs(media_target, exist_ok=True)

    created = updated = 0
    for filename, (name, description, price, stock) in CATALOG.items():
        source = os.path.join(IMAGE_DIR, filename)
        if not os.path.exists(source):
            print(f"SKIP {filename}: image missing")
            continue
        shutil.copy2(source, os.path.join(media_target, filename))
        medicine, was_created = Medicine.objects.update_or_create(
            pharmacy=pharmacy,
            name=name,
            defaults={
                "description": description,
                "price": price,
                "stock": stock,
                "image": f"medicines/{filename}",
            },
        )
        created += was_created
        updated += not was_created
    print(f"Catalog import complete: {created} created, {updated} updated, pharmacy={pharmacy.email}")


if __name__ == "__main__":
    main()
