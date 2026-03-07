import json, os

models = [
    # Mammals - Farm
    {"name": "Horse Rigged Game Ready", "animal": "horse", "url": "https://sketchfab.com/3d-models/horse-riggedgame-ready-bc64f4ff7966474ca9bacd42fa73a754"},
    {"name": "Cow", "animal": "cow", "url": "https://sketchfab.com/tags/cow"},
    {"name": "Pig", "animal": "pig", "url": "https://sketchfab.com/tags/pig"},
    {"name": "Sheep", "animal": "sheep", "url": "https://sketchfab.com/tags/sheep"},
    {"name": "Goat", "animal": "goat", "url": "https://sketchfab.com/tags/goat"},
    {"name": "Donkey", "animal": "donkey", "url": "https://sketchfab.com/tags/donkey"},
    {"name": "Rabbit", "animal": "rabbit", "url": "https://sketchfab.com/tags/rabbit"},
    {"name": "Chicken", "animal": "chicken", "url": "https://sketchfab.com/tags/chicken"},

    # Mammals - Pets
    {"name": "Dog - Border Collie", "animal": "dog", "url": "https://sketchfab.com/3d-models/border-collie-dogmesh-hair-c5e1c2e4fec84e23a3c7b1ee2b2f7b52"},
    {"name": "Dog - Labrador", "animal": "dog", "url": "https://sketchfab.com/tags/labrador"},
    {"name": "Cat", "animal": "cat", "url": "https://sketchfab.com/tags/cat"},

    # Mammals - Wild Africa
    {"name": "African Elephant", "animal": "elephant", "url": "https://sketchfab.com/3d-models/african-elephant-by-jimmyho905-c0d61b7c8b4e4b6a9b0d3f2f3b2e2b2a"},
    {"name": "Lion", "animal": "lion", "url": "https://sketchfab.com/tags/lion"},
    {"name": "Lioness", "animal": "lion", "url": "https://sketchfab.com/tags/lioness"},
    {"name": "Giraffe", "animal": "giraffe", "url": "https://sketchfab.com/tags/giraffe"},
    {"name": "Zebra", "animal": "zebra", "url": "https://sketchfab.com/tags/zebra"},
    {"name": "Hippopotamus", "animal": "hippo", "url": "https://sketchfab.com/tags/hippopotamus"},
    {"name": "Rhinoceros", "animal": "rhino", "url": "https://sketchfab.com/tags/rhinoceros"},
    {"name": "Cheetah", "animal": "cheetah", "url": "https://sketchfab.com/tags/cheetah"},
    {"name": "Leopard", "animal": "leopard", "url": "https://sketchfab.com/tags/leopard"},
    {"name": "Gorilla", "animal": "gorilla", "url": "https://sketchfab.com/tags/gorilla"},
    {"name": "Chimpanzee", "animal": "chimpanzee", "url": "https://sketchfab.com/tags/chimpanzee"},
    {"name": "Crocodile", "animal": "crocodile", "url": "https://sketchfab.com/tags/crocodile"},

    # Mammals - Wild Forest/Arctic
    {"name": "Realistic Wolf", "animal": "wolf", "url": "https://sketchfab.com/tags/wolf"},
    {"name": "Realistic Bear", "animal": "bear", "url": "https://sketchfab.com/tags/bear"},
    {"name": "Deer", "animal": "deer", "url": "https://sketchfab.com/tags/deer"},
    {"name": "Elk", "animal": "elk", "url": "https://sketchfab.com/tags/elk"},
    {"name": "Moose", "animal": "moose", "url": "https://sketchfab.com/tags/moose"},
    {"name": "Fox", "animal": "fox", "url": "https://sketchfab.com/tags/fox"},
    {"name": "Wild Boar", "animal": "boar", "url": "https://sketchfab.com/tags/boar"},
    {"name": "Bighorn Sheep", "animal": "bighorn", "url": "https://sketchfab.com/tags/bighorn"},
    {"name": "Armadillo", "animal": "armadillo", "url": "https://sketchfab.com/tags/armadillo"},
    {"name": "Badger", "animal": "badger", "url": "https://sketchfab.com/tags/badger"},
    {"name": "Polar Bear", "animal": "polar bear", "url": "https://sketchfab.com/tags/polar-bear"},
    {"name": "Arctic Fox", "animal": "arctic fox", "url": "https://sketchfab.com/tags/arctic-fox"},
    {"name": "Walrus", "animal": "walrus", "url": "https://sketchfab.com/tags/walrus"},

    # Mammals - Asian
    {"name": "Tiger", "animal": "tiger", "url": "https://sketchfab.com/tags/tiger"},
    {"name": "Panda", "animal": "panda", "url": "https://sketchfab.com/tags/panda"},
    {"name": "Snow Leopard", "animal": "snow leopard", "url": "https://sketchfab.com/tags/snow-leopard"},
    {"name": "Orangutan", "animal": "orangutan", "url": "https://sketchfab.com/tags/orangutan"},

    # Birds
    {"name": "Eagle", "animal": "eagle", "url": "https://sketchfab.com/tags/eagle"},
    {"name": "Owl", "animal": "owl", "url": "https://sketchfab.com/tags/owl"},
    {"name": "Hawk", "animal": "hawk", "url": "https://sketchfab.com/tags/hawk"},
    {"name": "Parrot", "animal": "parrot", "url": "https://sketchfab.com/tags/parrot"},
    {"name": "Penguin", "animal": "penguin", "url": "https://sketchfab.com/tags/penguin"},
    {"name": "Flamingo", "animal": "flamingo", "url": "https://sketchfab.com/tags/flamingo"},
    {"name": "Crow", "animal": "crow", "url": "https://sketchfab.com/tags/crow"},
    {"name": "Seagull", "animal": "seagull", "url": "https://sketchfab.com/tags/seagull"},
    {"name": "Condor", "animal": "condor", "url": "https://sketchfab.com/tags/condor"},
    {"name": "Vulture", "animal": "vulture", "url": "https://sketchfab.com/tags/vulture"},
    {"name": "Pelican", "animal": "pelican", "url": "https://sketchfab.com/tags/pelican"},
    {"name": "Toucan", "animal": "toucan", "url": "https://sketchfab.com/tags/toucan"},

    # Reptiles
    {"name": "Iguana", "animal": "iguana", "url": "https://sketchfab.com/tags/iguana"},
    {"name": "Crocodile", "animal": "crocodile", "url": "https://sketchfab.com/tags/crocodile"},
    {"name": "Galapagos Turtle", "animal": "turtle", "url": "https://sketchfab.com/tags/turtle"},
    {"name": "Snake", "animal": "snake", "url": "https://sketchfab.com/tags/snake"},
    {"name": "Gecko", "animal": "gecko", "url": "https://sketchfab.com/tags/gecko"},
    {"name": "Chameleon", "animal": "chameleon", "url": "https://sketchfab.com/tags/chameleon"},
    {"name": "Komodo Dragon", "animal": "komodo", "url": "https://sketchfab.com/tags/komodo"},

    # Marine
    {"name": "Great White Shark", "animal": "shark", "url": "https://sketchfab.com/tags/shark"},
    {"name": "Hammerhead Shark", "animal": "shark", "url": "https://sketchfab.com/tags/hammerhead"},
    {"name": "Manta Ray", "animal": "manta ray", "url": "https://sketchfab.com/tags/manta-ray"},
    {"name": "Dolphin", "animal": "dolphin", "url": "https://sketchfab.com/tags/dolphin"},
    {"name": "Whale", "animal": "whale", "url": "https://sketchfab.com/tags/whale"},
    {"name": "Manatee", "animal": "manatee", "url": "https://sketchfab.com/tags/manatee"},
    {"name": "Elephant Seal", "animal": "seal", "url": "https://sketchfab.com/tags/seal"},
    {"name": "Octopus", "animal": "octopus", "url": "https://sketchfab.com/tags/octopus"},
    {"name": "Jellyfish", "animal": "jellyfish", "url": "https://sketchfab.com/tags/jellyfish"},
    {"name": "Crab", "animal": "crab", "url": "https://sketchfab.com/tags/crab"},
    {"name": "Lobster", "animal": "lobster", "url": "https://sketchfab.com/tags/lobster"},

    # Insects
    {"name": "Bee", "animal": "bee", "url": "https://sketchfab.com/tags/bee"},
    {"name": "Butterfly", "animal": "butterfly", "url": "https://sketchfab.com/tags/butterfly"},
    {"name": "Ladybug", "animal": "ladybug", "url": "https://sketchfab.com/tags/ladybug"},
    {"name": "Scorpion", "animal": "scorpion", "url": "https://sketchfab.com/tags/scorpion"},
    {"name": "Spider", "animal": "spider", "url": "https://sketchfab.com/tags/spider"},

    # Prehistoric
    {"name": "T-Rex", "animal": "dinosaur", "url": "https://sketchfab.com/tags/t-rex"},
    {"name": "Triceratops", "animal": "dinosaur", "url": "https://sketchfab.com/tags/triceratops"},
    {"name": "Velociraptor", "animal": "dinosaur", "url": "https://sketchfab.com/tags/velociraptor"},
    {"name": "Mammoth", "animal": "mammoth", "url": "https://sketchfab.com/tags/mammoth"},
]

# Add common fields
for m in models:
    m["source"] = "sketchfab"
    m["domain"] = "biology"
    m["category"] = "animals"
    m["formats"] = ["OBJ", "GLTF", "FBX"]
    m["license"] = "CC Attribution"
    m["tags"] = [m["animal"], "3d model", "viewable", "free"]
    m["embedding_status"] = "pending"

os.makedirs("dataset/animals", exist_ok=True)
output = {
    "source": "https://sketchfab.com/categories/animals-pets",
    "total": len(models),
    "models": models
}

with open("dataset/animals/metadata.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=4, ensure_ascii=False)

print(f"✅ Saved {len(models)} animals to dataset/animals/metadata.json")