from huggingface_hub import snapshot_download

dataset_path = snapshot_download(
    repo_id="EPFL-CVLab/OpenMaterial",
    repo_type="dataset",
    allow_patterns=["*ablation*"]   # downloads small subset only
)

print("Downloaded to:", dataset_path)