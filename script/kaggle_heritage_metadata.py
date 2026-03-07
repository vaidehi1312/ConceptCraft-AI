import json, os

dataset_path = "dataset/high_fidelity_heritage"
models = []

for root, dirs, files in os.walk(dataset_path):
    for file in files:
        ext = file.split(".")[-1].lower()
        if ext in ["obj", "gltf", "glb", "ply", "stl", "fbx", "json", "csv"]:
            full_path = os.path.join(root, file)
            models.append({
                "name": file,
                "file_path": full_path,
                "format": ext.upper(),
                "source": "kaggle",
                "url": "https://www.kaggle.com/datasets/programmer3/high-fidelity-cultural-heritage-3d-dataset",
                "domain": "cultural_heritage",
                "category": "historical_sites",
                "tags": ["heritage", "monuments", "architecture"],
                "embedding_status": "pending"
            })

output = {
    "source": "https://www.kaggle.com/datasets/programmer3/high-fidelity-cultural-heritage-3d-dataset",
    "total": len(models),
    "models": models
}

with open(f"{dataset_path}/metadata.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=4, ensure_ascii=False)

print(f"✅ Found {len(models)} files → saved to dataset/high_fidelity_heritage/metadata.json")