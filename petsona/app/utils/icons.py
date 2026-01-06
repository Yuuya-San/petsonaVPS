# ---- SPECIES ICON MAP (CATEGORY ONLY) ----

SPECIES_ICON_MAP = {
    # 🐶 Dog
    "dog": "fa-solid fa-dog",
    "dogs": "fa-solid fa-dog",

    # 🐱 Cat
    "cat": "fa-solid fa-cat",
    "cats": "fa-solid fa-cat",

    # 🐟 Fishes
    "fish": "fa-solid fa-fish",
    "fishes": "fa-solid fa-fish",

    # 🐦 Birds
    "bird": "fa-solid fa-dove",
    "birds": "fa-solid fa-dove",

    # 🐭 Small Mammals
    "small mammal": "fa-solid fa-otter",
    "small mammals": "fa-solid fa-otter",

    # 🐍 Reptiles
    "reptile": "fa-solid fa-dragon",
    "reptiles": "fa-solid fa-dragon",

    # 🐸 Amphibians
    "amphibian": "fa-solid fa-frog",
    "amphibians": "fa-solid fa-frog",
}


def get_species_icon(name: str) -> str:
    """
    Returns the Font Awesome icon class for a species category.
    Falls back to paw icon only if the category is unknown.
    """
    if not name:
        return "fa-solid fa-paw"

    key = name.lower().strip()

    # Exact match first
    if key in SPECIES_ICON_MAP:
        return SPECIES_ICON_MAP[key]

    # Partial match (e.g. "Pet Birds", "Small Mammals Group")
    for species, icon in SPECIES_ICON_MAP.items():
        if species in key:
            return icon

    # Truly unknown category
    return "fa-solid fa-paw"
