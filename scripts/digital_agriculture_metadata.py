import json, os

models = [
    {
        "name": "Crops3D - Cabbage, Cotton, Maize, Potato, Rapeseed, Rice, Tomato, Wheat",
        "url": "https://www.nature.com/articles/s41597-024-04290-0",
        "download_url": "https://doi.org/10.1038/s41597-024-04290-0",
        "description": "Point cloud dataset of 8 crops: cabbage, cotton, maize, potato, rapeseed, rice, tomato, wheat in PLY format",
        "formats": ["PLY", "pointcloud"],
        "tags": ["crops", "pointcloud", "wheat", "maize", "tomato", "rice"]
    },
    {
        "name": "Pheno4D - Maize and Tomato Plant Point Clouds",
        "url": "https://www.ipb.uni-bonn.de/data/pheno4d/",
        "description": "244 point clouds of 7 maize and 7 tomato plants scanned at different growth stages with semantic labels",
        "formats": ["PLY", "pointcloud"],
        "tags": ["maize", "tomato", "phenotyping", "pointcloud", "growth stages"]
    },
    {
        "name": "PLANesT-3D - Plant Point Cloud Segmentation Dataset",
        "url": "https://arxiv.org/abs/2407.21150",
        "description": "34 real plant RGB point clouds from 3 species with semantic and instance labels",
        "formats": ["PLY", "pointcloud"],
        "tags": ["plant segmentation", "pointcloud", "RGB", "semantic labels"]
    },
    {
        "name": "Soybean-MVS - 3D Soybean Plant Models",
        "url": "https://www.mdpi.com/2077-0472/13/7/1321",
        "description": "102 soybean 3D plant models from multi-view stereo across 13 growth stages",
        "formats": ["PLY", "pointcloud"],
        "tags": ["soybean", "3D reconstruction", "growth stages", "MVS"]
    },
    {
        "name": "Wheat Plant 3D Dataset - Nottingham",
        "url": "https://plantimages.nottingham.ac.uk/",
        "download_url": "https://doi.org/10.5524/102661",
        "description": "High-fidelity wheat plant 3D reconstructions using 3D Gaussian Splatting and NeRF with point clouds",
        "formats": ["PLY", "pointcloud", "NeRF"],
        "tags": ["wheat", "3DGS", "NeRF", "pointcloud", "high fidelity"]
    },
    {
        "name": "Sketchfab Agriculture 3D Models",
        "url": "https://sketchfab.com/tags/agriculture",
        "description": "Free viewable 3D agriculture models including crops, farm equipment and plants",
        "formats": ["OBJ", "GLTF", "FBX"],
        "tags": ["crops", "farm", "agriculture", "viewable", "free"]
    },
    {
        "name": "Sketchfab Crops 3D Models",
        "url": "https://sketchfab.com/tags/crops",
        "description": "Free viewable 3D crop models including tomatoes, potatoes, carrots and wheat",
        "formats": ["OBJ", "GLTF"],
        "tags": ["crops", "tomato", "wheat", "potato", "viewable"]
    },
    {
        "name": "Sketchfab Farm 3D Models",
        "url": "https://sketchfab.com/tags/farm",
        "description": "Free viewable 3D farm environment models",
        "formats": ["OBJ", "GLTF"],
        "tags": ["farm", "environment", "agriculture", "viewable"]
    },
    {
        "name": "P3D - Plant 3D Point Cloud Toolkit",
        "url": "https://github.com/iziamtso/P3D",
        "description": "Plant point cloud dataset with tomato and other plant scans in PCD format with phenotyping labels",
        "formats": ["PCD", "OBJ", "pointcloud"],
        "tags": ["tomato", "phenotyping", "pointcloud", "segmentation"]
    }
]

# Add common fields
for m in models:
    m["source"] = "research"
    m["domain"] = "agriculture"
    m["category"] = "crop_3d_models"
    m["license"] = "open"
    m["embedding_status"] = "pending"

os.makedirs("dataset/digital_agriculture", exist_ok=True)
output = {
    "source": "multiple",
    "total": len(models),
    "models": models
}

with open("dataset/digital_agriculture/metadata.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=4, ensure_ascii=False)

print(f"✅ Saved {len(models)} agriculture 3D datasets to dataset/digital_agriculture/metadata.json")