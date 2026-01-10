# ==========================================
# 🇵🇭 PHILIPPINE PET SPECIES → ICON MAP
# (Breed-capable species only)
# ==========================================

SPECIES_ICON_MAP = {

    # 🐶 Dogs
    "dog": "fa-solid fa-dog",

    # 🐱 Cats
    "cat": "fa-solid fa-cat",

    # 🐦 Birds
    "lovebird": "fa-solid fa-dove",
    "cockatiel": "fa-solid fa-dove",
    "budgerigar": "fa-solid fa-dove",
    "budgie": "fa-solid fa-dove",
    "african grey": "fa-solid fa-dove",
    "macaw": "fa-solid fa-dove",
    "cockatoo": "fa-solid fa-dove",
    "conure": "fa-solid fa-dove",
    "eclectus": "fa-solid fa-dove",
    "canary": "fa-solid fa-dove",
    "finch": "fa-solid fa-dove",
    "pigeon": "fa-solid fa-dove",
    "dove": "fa-solid fa-dove",
    "myna": "fa-solid fa-dove",
    "quaker parrot": "fa-solid fa-dove",
    "lorikeet": "fa-solid fa-dove",

    # 🐟 Fish
    "betta": "fa-solid fa-fish",
    "goldfish": "fa-solid fa-fish",
    "koi": "fa-solid fa-fish",
    "guppy": "fa-solid fa-fish",
    "molly": "fa-solid fa-fish",
    "platy": "fa-solid fa-fish",
    "swordtail": "fa-solid fa-fish",
    "tetra": "fa-solid fa-fish",
    "angelfish": "fa-solid fa-fish",
    "discus": "fa-solid fa-fish",
    "arowana": "fa-solid fa-fish",
    "flowerhorn": "fa-solid fa-fish",
    "oscar": "fa-solid fa-fish",
    "pleco": "fa-solid fa-fish",
    "plecostomus": "fa-solid fa-fish",
    "danio": "fa-solid fa-fish",
    "zebra danio": "fa-solid fa-fish",
    "tiger barb": "fa-solid fa-fish",

    # 🐹 Small mammals
    "hamster": "fa-solid fa-otter",
    "guinea pig": "fa-solid fa-otter",
    "rabbit": "fa-solid fa-otter",
    "mouse": "fa-solid fa-otter",
    "rat": "fa-solid fa-otter",
    "chinchilla": "fa-solid fa-otter",
    "ferret": "fa-solid fa-otter",
    "hedgehog": "fa-solid fa-otter",
    "sugar glider": "fa-solid fa-otter",

    # 🐍 Reptiles
    "ball python": "fa-solid fa-dragon",
    "corn snake": "fa-solid fa-dragon",
    "king snake": "fa-solid fa-dragon",
    "leopard gecko": "fa-solid fa-dragon",
    "crested gecko": "fa-solid fa-dragon",
    "bearded dragon": "fa-solid fa-dragon",
    "iguana": "fa-solid fa-dragon",
    "red-eared slider": "fa-solid fa-dragon",
    "russian tortoise": "fa-solid fa-dragon",
    "sulcata": "fa-solid fa-dragon",

    # 🐸 Amphibians
    "pacman frog": "fa-solid fa-frog",
    "tree frog": "fa-solid fa-frog",
    "african clawed frog": "fa-solid fa-frog",
    "axolotl": "fa-solid fa-frog",
    "fire-bellied toad": "fa-solid fa-frog",

    # 🕷️ Invertebrates
    "tarantula": "fa-solid fa-spider",
    "scorpion": "fa-solid fa-spider",
    "mantis": "fa-solid fa-spider",
    "stick insect": "fa-solid fa-spider",
    "beetle": "fa-solid fa-spider",
    "giant african land snail": "fa-solid fa-spider",
}


# ==========================================
# ICON RESOLVER (DB SAFE)
# ==========================================

def get_species_icon(name: str) -> str:
    """
    Works with:
    'Dog'
    'Betta (Siamese Fighting Fish)'
    'African Grey Parrot'
    'Red-Eared Slider Turtle'
    'Golden Retriever Dog'
    """

    if not name:
        return "fa-solid fa-paw"

    key = name.lower().strip()

    # Exact match
    if key in SPECIES_ICON_MAP:
        return SPECIES_ICON_MAP[key]

    # Partial match (for DB strings like "Betta Fish", "Lovebird Peach")
    for species, icon in SPECIES_ICON_MAP.items():
        if species in key:
            return icon

    return "fa-solid fa-paw"
