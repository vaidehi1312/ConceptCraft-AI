import os
import json

dataset_path = "openmaterial_extracted"
data = []

for root, dirs, files in os.walk(dataset_path):
    for file in files:
        if file.endswith(".png"):
            path = os.path.join(root, file)

            data.append({
                "image_path": path
            })

with open("openmaterial_dataset.json", "w") as f:
    json.dump(data, f, indent=4)

print("Dataset JSON created!")