"""Catalogue fields keyed by stable subcategory IDs from the pharmacy taxonomy."""

PREFIX = "sub-category-healthmart-pharmacy-wellness-and-personal-care-"


def text(key, label):
    return {"key": key, "label": label, "type": "text"}


def count(key, label):
    return {"key": key, "label": label, "type": "integer", "min": 1}


ACTIVE = text("active_ingredients", "Active ingredient(s)")
STRENGTH = text("strength", "Strength with unit")
FORM = text("dosage_form", "Dosage form")
PACK = count("units_per_pack", "Units per pack")
VOLUME = text("net_volume", "Net volume with unit")
CONTENT = text("net_contents", "Net contents with unit")
CONCENTRATION = text("concentration", "Concentration with unit")
INGREDIENT = text("ingredients", "Ingredient(s)")
SERVING = text("serving_size", "Serving size")
PER_SERVING = text("amount_per_serving", "Amount per serving with unit")
SERVINGS = count("servings_per_pack", "Servings per pack")
FLAVOR = text("flavor", "Flavour")
BOTANICAL = text("botanical_name", "Botanical name")
DEVICE = (text("brand", "Brand"), text("model", "Model"))
POWER = text("power_source", "Power source")
RANGE = text("measurement_range", "Measurement range with unit")
TEST_TYPE = text("test_type", "Test type or target")
SAMPLE = text("sample_type", "Sample type")
TESTS = count("tests_per_pack", "Tests per pack")
CARE = (text("product_type", "Product type"), INGREDIENT, CONTENT)
SKIN = (*CARE, text("skin_type", "Skin type"))
HAIR = (*CARE, text("hair_type", "Hair type"))
ORAL = (*CARE, text("fluoride_content", "Fluoride content if listed"))
SOLID_MEDICINE = (ACTIVE, STRENGTH, FORM, PACK)
SUPPLEMENT = (INGREDIENT, PER_SERVING, SERVING, SERVINGS)
NUTRITION = (*SUPPLEMENT, FLAVOR, CONTENT)
HERBAL = (BOTANICAL, text("plant_part", "Plant part"), FORM, STRENGTH, CONTENT)
TEST_KIT = (TEST_TYPE, SAMPLE, TESTS, text("result_time", "Result time with unit"))

TEMPLATES = {
    "over-the-counter-medications": {
        "pain-relievers": SOLID_MEDICINE,
        "cold-and-flu-medicines": (*SOLID_MEDICINE, VOLUME),
        "allergy-relief": SOLID_MEDICINE,
        "digestive-health": (*SOLID_MEDICINE, VOLUME),
        "cough-syrups": (ACTIVE, CONCENTRATION, VOLUME, FLAVOR),
        "antiseptics": (ACTIVE, CONCENTRATION, FORM, CONTENT),
        "oral-rehydration-salts": (text("composition", "Labelled composition"), text("sachet_weight", "Sachet weight with unit"), PACK),
    },
    "vitamins-supplements-and-nutrition": {
        "vitamins-and-supplements": (*SUPPLEMENT, FORM),
        "protein-powders-and-nutrition-bars": (*NUTRITION, FORM, text("protein_per_serving", "Protein per serving with unit")),
        "herbal-remedies": HERBAL,
        "collagen": (*SUPPLEMENT, text("collagen_source", "Collagen source"), text("collagen_type", "Collagen type"), FORM),
        "protein": (*NUTRITION, text("protein_source", "Protein source"), text("protein_per_serving", "Protein per serving with unit")),
        "dietary-fiber": (*SUPPLEMENT, text("fiber_type", "Fibre type"), FORM),
        "sports-nutrition": (*NUTRITION, text("product_type", "Product type")),
        "calcium-iron-zinc-and-selenium": (*SUPPLEMENT, FORM),
        "plant-extracts": (*HERBAL, text("extract_ratio", "Extract ratio")),
    },
    "personal-care-and-hygiene": {
        "skincare-moisturizers-cleansers": SKIN,
        "haircare-shampoos-conditioners": HAIR,
        "oral-care-toothpaste-mouthwash": ORAL,
        "sanitizers": (ACTIVE, CONCENTRATION, FORM, VOLUME),
        "deodorants": (*CARE, text("scent", "Scent")),
        "feminine-care": (*CARE, text("size", "Size"), text("absorbency", "Absorbency"), PACK),
        "incontinence-care": (text("product_type", "Product type"), text("size", "Size"), text("absorbency", "Absorbency"), PACK),
    },
    "home-testing-and-monitoring": {
        "testing-kits": TEST_KIT,
        "glucose-meters": (*DEVICE, text("compatible_strips", "Compatible test strips"), text("display_unit", "Display unit"), text("included_items", "Included items"), POWER),
        "thermometers": (*DEVICE, text("measurement_method", "Measurement method"), RANGE, POWER),
        "blood-pressure-monitors": (*DEVICE, text("cuff_range", "Cuff size range with unit"), POWER, text("included_items", "Included items")),
        "pulse-oximeters": (*DEVICE, RANGE, text("sensor_type", "Sensor type"), POWER),
        "pregnancy-tests": (*TEST_KIT, text("test_format", "Test format")),
        "rapid-test-kits": TEST_KIT,
    },
    "other-health-and-wellness": {
        "personal-care-products": CARE,
        "skincare-moisturizers-cleansers": SKIN,
        "haircare-shampoos-conditioners": HAIR,
        "oral-care-toothpaste-mouthwash": ORAL,
        "health-and-wellness": (text("product_type", "Product type"), text("brand", "Brand"), CONTENT),
        "slimming-tea": (INGREDIENT, FLAVOR, count("tea_bags", "Tea bags per pack"), CONTENT),
        "other-health-care-supplements": (*SUPPLEMENT, FORM, CONTENT),
    },
}

FIELDS_BY_NODE = {
    f"{PREFIX}{category}-{subcategory}": fields
    for category, templates in TEMPLATES.items()
    for subcategory, fields in templates.items()
}
