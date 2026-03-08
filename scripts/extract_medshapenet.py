import numpy as np
import os
import json

dataset_path = "../datasets/medshapenet/medshapenetcore_ASOCA.npz"

# allow pickle objects
data = np.load(dataset_path, allow_pickle=True)

print("Keys inside dataset:", data.files)

dataset = data["data"].item()

print("Dataset loaded")
print("Top level keys:", dataset.keys())