import json, os

models = [
    {
        "name": "Buckingham Palace",
        "sketchfab_short_url": "https://skfb.ly/ptsFD",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/Buckingham.png",
        "tags": ["palace", "architecture", "UK", "london"]
    },
    {
        "name": "Cambridge Campus",
        "sketchfab_short_url": "https://skfb.ly/ptsFK",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/one_page.png",
        "tags": ["campus", "urban", "architecture", "VR"]
    },
    {
        "name": "Egyptian Pyramids and Sphinx",
        "sketchfab_short_url": "https://skfb.ly/ptsFL",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/pyramid.png",
        "tags": ["egypt", "pyramid", "ancient", "archaeology"]
    },
    {
        "name": "Louvre Museum",
        "sketchfab_short_url": "https://skfb.ly/ptsFM",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/louvre.png",
        "tags": ["museum", "paris", "architecture", "france"]
    },
    {
        "name": "Leaning Tower of Pisa",
        "sketchfab_short_url": "https://skfb.ly/ptsFN",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/Italy.png",
        "tags": ["italy", "tower", "monument", "VR"]
    },
    {
        "name": "Stonehenge",
        "sketchfab_short_url": "https://skfb.ly/ptsFP",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/stonehenge.png",
        "tags": ["stonehenge", "prehistoric", "UK", "archaeology"]
    },
    {
        "name": "Petra",
        "sketchfab_short_url": "https://skfb.ly/pt9ro",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/petra.png",
        "tags": ["petra", "jordan", "ancient", "archaeology", "VR"]
    },
    {
        "name": "Trafalgar Square",
        "sketchfab_short_url": "https://skfb.ly/pt9rF",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/trafalgar.png",
        "tags": ["london", "square", "statues", "architecture"]
    },
    {
        "name": "National Art Gallery",
        "sketchfab_short_url": "https://skfb.ly/pt9sF",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/gallery2.png",
        "tags": ["gallery", "museum", "interior", "art", "VR"]
    },
    {
        "name": "Forbidden City",
        "sketchfab_short_url": "https://skfb.ly/pt9sR",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/gugong.png",
        "tags": ["china", "forbidden city", "heritage", "architecture"]
    },
    {
        "name": "Longmen Grottoes",
        "sketchfab_short_url": "https://skfb.ly/pt9tr",
        "thumbnail": "https://github.com/X-Intelligence-Labs/CULTURE3D/raw/main/images/longmen_all.png",
        "tags": ["china", "grottoes", "carvings", "buddhist", "VR"]
    }
]

# Add common fields
for m in models:
    m["source"] = "sketchfab"
    m["domain"] = "cultural_heritage"
    m["category"] = "3d_reconstruction"
    m["formats"] = ["PLY", "PCD", "COLMAP"]
    m["license"] = "open"
    m["embedding_status"] = "pending"
    # Add view URL - clicking this opens the 3D model directly on Sketchfab
    m["view_url"] = m["sketchfab_short_url"]

os.makedirs("dataset/CULTURE3D", exist_ok=True)
output = {
    "source": "https://github.com/X-Intelligence-Labs/CULTURE3D",
    "google_drive": "https://drive.google.com/drive/folders/1LaxcwUI1R1trs6lmHGU_3odBo6B8xiob",
    "total": len(models),
    "models": models
}

with open("dataset/CULTURE3D/metadata.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=4, ensure_ascii=False)

print(f"✅ Saved {len(models)} models to dataset/CULTURE3D/metadata.json")