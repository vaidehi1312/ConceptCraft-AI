import zipfile

zip_path = "modelnet40_dataset/archive.zip"
extract_path = "modelnet40_dataset"

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_path)

print("ModelNet40 extraction complete!")