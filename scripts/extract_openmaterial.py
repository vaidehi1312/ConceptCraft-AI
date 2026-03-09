import tarfile
import os

dataset_folder = r"C:\Users\karee\.cache\huggingface\hub\datasets--EPFL-CVLab--OpenMaterial"

extract_folder = "openmaterial_extracted"

os.makedirs(extract_folder, exist_ok=True)

for root, dirs, files in os.walk(dataset_folder):
    for file in files:
        if file.endswith(".tar"):
            tar_path = os.path.join(root, file)

            print("Extracting:", tar_path)

            with tarfile.open(tar_path) as tar:
                tar.extractall(extract_folder)

print("Extraction complete!")