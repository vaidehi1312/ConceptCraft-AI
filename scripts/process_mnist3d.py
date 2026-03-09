import os
import json

dataset_path = "mnist3d_dataset"
data = []

for root, dirs, files in os.walk(dataset_path):
    for file in files:
        data.append({
            "file": file,
            "path": os.path.join(root, file)
        })

with open("mnist3d_dataset.json", "w") as f:
    json.dump(data, f, indent=4)

print("MNIST3D dataset JSON created!")