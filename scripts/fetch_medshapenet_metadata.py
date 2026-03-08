"""
fetch_medshapenet_metadata.py
------------------------------
Generates medshapenet_metadata.json for FAISS indexing.
No local downloads. No API calls. Metadata only.

WHY NO API CALLS:
  The MedShapeNet 2.0 Python API is currently under heavy construction.
  Only search_by_name() and search_and_download_by_name() work for the
  full Sciebo-hosted database. There is no endpoint to list/paginate
  all shapes as structured metadata JSON.

STRATEGY:
  - Hardcode all 23 known sub-datasets with rich metadata per anatomy
  - Cover every named anatomy across: bones, organs, vessels, muscles,
    brain structures, tumors, surgical instruments
  - Each entry has: name, anatomy_type, body_system, description, tags,
    dataset_source, shape_format, render_type, search_key (for API lookup)
  - On user query: FAISS finds best match → use search_key to call
    msn.search_and_download_by_name(search_key) at runtime

RUNTIME FETCH (when user actually requests a shape):
  pip install MedShapeNet
  from MedShapeNet import MedShapeNet
  msn = MedShapeNet()
  msn.search_and_download_by_name("liver", output_dir="./cache/")

Web interface (embed or link):
  https://medshapenet.ikim.nrw/

Output:
  metadata/medshapenet_metadata.json

License: varies per sub-dataset (CC BY 4.0, CC0, MIT, etc.) — see license field
"""

import json
import os
from collections import Counter

OUTPUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "metadata")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "medshapenet_metadata.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# ALL 23 MEDSHAPENET SUB-DATASETS
# Source: MedShapeNet paper (arXiv:2308.16139) + GitHub dataset list
# ---------------------------------------------------------------------------
DATASETS = [
    {
        "dataset_key":   "AORTA",
        "dataset_name":  "Aortic Vessel Trees",
        "license":       "CC BY 4.0",
        "shape_count":   "~1000",
        "anatomy_types": ["vessel"],
        "body_systems":  ["cardiovascular"],
    },
    {
        "dataset_key":   "BraTS",
        "dataset_name":  "Brain Tumor Segmentation (BraTS)",
        "license":       "CC BY 4.0",
        "shape_count":   "~2000",
        "anatomy_types": ["brain", "tumor"],
        "body_systems":  ["nervous"],
    },
    {
        "dataset_key":   "Calgary-Campinas",
        "dataset_name":  "Calgary-Campinas Brain Structures",
        "license":       "Research only",
        "shape_count":   "~350",
        "anatomy_types": ["brain"],
        "body_systems":  ["nervous"],
    },
    {
        "dataset_key":   "CrossMoDA",
        "dataset_name":  "Brain Tumor and Cochlea (CrossMoDA)",
        "license":       "CC BY 4.0",
        "shape_count":   "~300",
        "anatomy_types": ["brain", "tumor", "cochlea"],
        "body_systems":  ["nervous", "sensory"],
    },
    {
        "dataset_key":   "CT-ORG",
        "dataset_name":  "CT-ORG Multiple Organ Segmentation",
        "license":       "CC0 1.0",
        "shape_count":   "~140",
        "anatomy_types": ["organ"],
        "body_systems":  ["digestive", "urinary", "respiratory"],
    },
    {
        "dataset_key":   "DigitalBodyPreservation",
        "dataset_name":  "Digital Body Preservation",
        "license":       "CC BY 4.0",
        "shape_count":   "~50",
        "anatomy_types": ["whole_body"],
        "body_systems":  ["musculoskeletal"],
    },
    {
        "dataset_key":   "EMIDEC",
        "dataset_name":  "Myocardium Segmentation (EMIDEC)",
        "license":       "CC BY-NC-SA 4.0",
        "shape_count":   "~150",
        "anatomy_types": ["heart", "myocardium"],
        "body_systems":  ["cardiovascular"],
    },
    {
        "dataset_key":   "FacialModels",
        "dataset_name":  "Facial Models for AR",
        "license":       "CC BY 4.0",
        "shape_count":   "~500",
        "anatomy_types": ["face", "skull"],
        "body_systems":  ["musculoskeletal"],
    },
    {
        "dataset_key":   "FLARE",
        "dataset_name":  "FLARE 13 Abdominal Organs",
        "license":       "CC BY 4.0",
        "shape_count":   "~2000",
        "anatomy_types": ["organ"],
        "body_systems":  ["digestive", "urinary", "endocrine"],
    },
    {
        "dataset_key":   "GLISRT",
        "dataset_name":  "GLIS-RT Brain Structures",
        "license":       "TCIA Restricted",
        "shape_count":   "~230",
        "anatomy_types": ["brain"],
        "body_systems":  ["nervous"],
    },
    {
        "dataset_key":   "HCP",
        "dataset_name":  "Human Connectome Project Brain-Skull",
        "license":       "Data Use Terms",
        "shape_count":   "~1100",
        "anatomy_types": ["brain", "skull"],
        "body_systems":  ["nervous", "musculoskeletal"],
    },
    {
        "dataset_key":   "HECKTOR",
        "dataset_name":  "Head and Neck Tumor (HECKTOR)",
        "license":       "CC BY 4.0",
        "shape_count":   "~500",
        "anatomy_types": ["tumor", "head", "neck"],
        "body_systems":  ["oncology"],
    },
    {
        "dataset_key":   "ISLES22",
        "dataset_name":  "Ischemic Stroke Lesion (ISLES22)",
        "license":       "CC BY 4.0",
        "shape_count":   "~400",
        "anatomy_types": ["brain", "lesion"],
        "body_systems":  ["nervous", "cardiovascular"],
    },
    {
        "dataset_key":   "KiTS21",
        "dataset_name":  "Kidney and Kidney Tumor (KiTS21)",
        "license":       "MIT",
        "shape_count":   "~600",
        "anatomy_types": ["kidney", "tumor"],
        "body_systems":  ["urinary", "oncology"],
    },
    {
        "dataset_key":   "LiTS",
        "dataset_name":  "Liver Tumor Segmentation (LiTS)",
        "license":       "CC BY 4.0",
        "shape_count":   "~400",
        "anatomy_types": ["liver", "tumor"],
        "body_systems":  ["digestive", "oncology"],
    },
    {
        "dataset_key":   "MSD",
        "dataset_name":  "Medical Segmentation Decathlon (MSD)",
        "license":       "CC BY-SA 4.0",
        "shape_count":   "~5000",
        "anatomy_types": ["organ", "tumor"],
        "body_systems":  ["digestive", "nervous", "respiratory", "oncology"],
    },
    {
        "dataset_key":   "SegTHOR",
        "dataset_name":  "SegTHOR Thoracic Organs",
        "license":       "CC BY 4.0",
        "shape_count":   "~240",
        "anatomy_types": ["heart", "aorta", "trachea", "esophagus"],
        "body_systems":  ["cardiovascular", "respiratory", "digestive"],
    },
    {
        "dataset_key":   "SUDMEX",
        "dataset_name":  "SUDMEX CONN Brain Connectivity",
        "license":       "CC BY 4.0",
        "shape_count":   "~200",
        "anatomy_types": ["brain"],
        "body_systems":  ["nervous"],
    },
    {
        "dataset_key":   "TotalSegmentator",
        "dataset_name":  "TotalSegmentator Whole Body",
        "license":       "CC BY 4.0",
        "shape_count":   "~50000",
        "anatomy_types": ["whole_body", "organ", "bone", "muscle", "vessel"],
        "body_systems":  ["musculoskeletal", "digestive", "cardiovascular", "respiratory", "urinary"],
    },
    {
        "dataset_key":   "VerSe",
        "dataset_name":  "VerSe Vertebrae Segmentation",
        "license":       "CC BY 4.0",
        "shape_count":   "~3000",
        "anatomy_types": ["vertebra", "spine"],
        "body_systems":  ["musculoskeletal"],
    },
    {
        "dataset_key":   "SurgicalInstruments",
        "dataset_name":  "Surgical Instruments 3D Models",
        "license":       "CC BY 4.0",
        "shape_count":   "~200",
        "anatomy_types": ["surgical_instrument"],
        "body_systems":  ["medical_device"],
    },
    {
        "dataset_key":   "LUNA16",
        "dataset_name":  "LUNA16 Lung Nodules",
        "license":       "CC BY 4.0",
        "shape_count":   "~1000",
        "anatomy_types": ["lung", "nodule", "tumor"],
        "body_systems":  ["respiratory", "oncology"],
    },
    {
        "dataset_key":   "CHAOS",
        "dataset_name":  "CHAOS Abdominal Organs",
        "license":       "CC BY 4.0",
        "shape_count":   "~120",
        "anatomy_types": ["liver", "kidney", "spleen"],
        "body_systems":  ["digestive", "urinary"],
    },
]

# ---------------------------------------------------------------------------
# INDIVIDUAL ANATOMY ENTRIES
# Each is one specific anatomy that FAISS can match to a user query
# search_key → passed directly to msn.search_and_download_by_name()
# ---------------------------------------------------------------------------
ANATOMIES = [

    # ── BRAIN & NERVOUS SYSTEM ────────────────────────────────────────────
    {
        "name": "Brain",
        "search_key": "brain",
        "anatomy_type": "organ",
        "body_system": "nervous",
        "description": "Whole brain 3D shape extracted from MRI scans. Includes cortical surface, white matter, and subcortical structures. Used for brain morphology analysis, tumor classification, and neurological condition studies.",
        "tags": ["brain", "organ", "nervous system", "MRI", "cortex", "white matter", "neurology", "3D shape", "anatomy"],
        "datasets": ["BraTS", "Calgary-Campinas", "HCP", "GLISRT", "SUDMEX"],
        "pathological_variants": ["brain tumor", "glioma", "stroke lesion"],
    },
    {
        "name": "Brain Tumor (Glioma)",
        "search_key": "brain tumor",
        "anatomy_type": "tumor",
        "body_system": "nervous",
        "description": "3D shapes of brain tumors including glioblastoma, meningioma, and metastatic lesions extracted from BraTS MRI dataset. Includes both tumorous and healthy brain shapes for classification benchmarks.",
        "tags": ["brain tumor", "glioma", "glioblastoma", "tumor", "cancer", "MRI", "oncology", "segmentation", "3D shape"],
        "datasets": ["BraTS", "HECKTOR"],
        "pathological_variants": ["glioblastoma", "meningioma", "metastasis"],
    },
    {
        "name": "Cochlea",
        "search_key": "cochlea",
        "anatomy_type": "organ",
        "body_system": "sensory",
        "description": "3D shape of the cochlea — the spiral-shaped hearing organ of the inner ear. Extracted from CT scans, used for cochlear implant planning and auditory research.",
        "tags": ["cochlea", "ear", "inner ear", "hearing", "sensory", "CT", "implant planning", "3D shape", "anatomy"],
        "datasets": ["CrossMoDA"],
        "pathological_variants": [],
    },
    {
        "name": "Ischemic Stroke Lesion",
        "search_key": "stroke lesion",
        "anatomy_type": "lesion",
        "body_system": "nervous",
        "description": "3D shapes of ischemic stroke lesions in the brain from ISLES22 dataset. Used for stroke outcome prediction, rehabilitation planning, and understanding infarct patterns.",
        "tags": ["stroke", "ischemic", "lesion", "brain", "infarct", "MRI", "neurology", "3D shape", "pathology"],
        "datasets": ["ISLES22"],
        "pathological_variants": ["acute stroke", "chronic infarct"],
    },

    # ── SKULL & FACIAL ────────────────────────────────────────────────────
    {
        "name": "Skull",
        "search_key": "skull",
        "anatomy_type": "bone",
        "body_system": "musculoskeletal",
        "description": "Complete 3D skull model from CT scans. Includes cranium and mandible. Used for forensic facial reconstruction, surgical planning, and cranial implant design.",
        "tags": ["skull", "bone", "cranium", "mandible", "CT", "forensic", "surgical planning", "3D shape", "anatomy"],
        "datasets": ["HCP", "FacialModels"],
        "pathological_variants": ["skull fracture", "cranial defect"],
    },
    {
        "name": "Face / Facial Surface",
        "search_key": "face",
        "anatomy_type": "surface",
        "body_system": "musculoskeletal",
        "description": "3D facial surface models for augmented reality applications and forensic reconstruction. Paired with skull shapes for skull-to-face reconstruction tasks.",
        "tags": ["face", "facial", "surface", "skin", "augmented reality", "XR", "forensic", "reconstruction", "3D shape"],
        "datasets": ["FacialModels", "HCP"],
        "pathological_variants": [],
    },
    {
        "name": "Head and Neck Tumor",
        "search_key": "head neck tumor",
        "anatomy_type": "tumor",
        "body_system": "oncology",
        "description": "3D tumor shapes in the head and neck region from HECKTOR dataset. Includes oropharyngeal tumors from PET-CT scans, used for radiotherapy planning.",
        "tags": ["head", "neck", "tumor", "cancer", "PET-CT", "oropharynx", "radiotherapy", "oncology", "3D shape"],
        "datasets": ["HECKTOR"],
        "pathological_variants": ["oropharyngeal cancer", "lymph node metastasis"],
    },

    # ── HEART & CARDIOVASCULAR ────────────────────────────────────────────
    {
        "name": "Heart",
        "search_key": "heart",
        "anatomy_type": "organ",
        "body_system": "cardiovascular",
        "description": "Whole heart 3D shape from cardiac MRI or CT. Includes all four chambers (left/right ventricle, left/right atrium). Used for cardiac function analysis, surgical planning, and 3D printing of heart models.",
        "tags": ["heart", "cardiac", "organ", "ventricle", "atrium", "MRI", "CT", "cardiovascular", "3D shape", "anatomy"],
        "datasets": ["EMIDEC", "SegTHOR", "TotalSegmentator"],
        "pathological_variants": ["myocardial infarction", "cardiomyopathy"],
    },
    {
        "name": "Myocardium",
        "search_key": "myocardium",
        "anatomy_type": "tissue",
        "body_system": "cardiovascular",
        "description": "3D shape of the myocardium (heart muscle) from EMIDEC dataset. Includes normal and pathological (infarction) myocardium shapes for cardiac ML benchmarks.",
        "tags": ["myocardium", "heart muscle", "cardiac", "infarction", "pathology", "MRI", "3D shape", "cardiovascular"],
        "datasets": ["EMIDEC"],
        "pathological_variants": ["myocardial infarction"],
    },
    {
        "name": "Aorta",
        "search_key": "aorta",
        "anatomy_type": "vessel",
        "body_system": "cardiovascular",
        "description": "Complete aortic vessel tree 3D shape including ascending aorta, aortic arch, descending thoracic, and abdominal aorta. Used for aneurysm detection, stent planning, and cardiovascular research.",
        "tags": ["aorta", "vessel", "cardiovascular", "aneurysm", "CT", "vascular", "aortic arch", "3D shape", "anatomy"],
        "datasets": ["AORTA", "SegTHOR", "TotalSegmentator"],
        "pathological_variants": ["aortic aneurysm", "aortic dissection"],
    },
    {
        "name": "Pulmonary Artery",
        "search_key": "pulmonary artery",
        "anatomy_type": "vessel",
        "body_system": "cardiovascular",
        "description": "3D shape of the pulmonary artery tree extracted from CT pulmonary angiography. Used for pulmonary embolism analysis and cardiac hemodynamics modeling.",
        "tags": ["pulmonary artery", "vessel", "lung", "cardiovascular", "CT", "embolism", "3D shape", "anatomy"],
        "datasets": ["TotalSegmentator"],
        "pathological_variants": ["pulmonary embolism"],
    },
    {
        "name": "Coronary Arteries",
        "search_key": "coronary artery",
        "anatomy_type": "vessel",
        "body_system": "cardiovascular",
        "description": "3D shapes of coronary arteries from coronary CT angiography. Diseased coronary arteries with stenosis and calcification from patients with coronary artery disease.",
        "tags": ["coronary", "artery", "vessel", "heart", "stenosis", "calcification", "CT", "cardiovascular", "3D shape"],
        "datasets": ["TotalSegmentator"],
        "pathological_variants": ["coronary artery disease", "stenosis"],
    },

    # ── LUNGS & RESPIRATORY ───────────────────────────────────────────────
    {
        "name": "Lung",
        "search_key": "lung",
        "anatomy_type": "organ",
        "body_system": "respiratory",
        "description": "3D shape of the lungs (left and right) from CT scans. Used for lung cancer screening, COPD analysis, COVID-19 lesion assessment, and surgical planning for lung resection.",
        "tags": ["lung", "organ", "respiratory", "CT", "cancer", "COPD", "COVID-19", "nodule", "3D shape", "anatomy"],
        "datasets": ["LUNA16", "CT-ORG", "TotalSegmentator", "MSD"],
        "pathological_variants": ["lung nodule", "lung cancer", "pneumonia"],
    },
    {
        "name": "Lung Nodule",
        "search_key": "lung nodule",
        "anatomy_type": "nodule",
        "body_system": "respiratory",
        "description": "3D shapes of pulmonary nodules from LUNA16 dataset. Includes benign and potentially malignant nodules for lung cancer screening and CAD system development.",
        "tags": ["lung nodule", "nodule", "lung", "cancer screening", "CT", "LUNA16", "pulmonary", "3D shape", "oncology"],
        "datasets": ["LUNA16"],
        "pathological_variants": ["malignant nodule", "benign nodule"],
    },
    {
        "name": "Trachea",
        "search_key": "trachea",
        "anatomy_type": "organ",
        "body_system": "respiratory",
        "description": "3D shape of the trachea (windpipe) and main bronchi from CT. Part of the SegTHOR thoracic dataset. Used for airway stent planning and ventilation modeling.",
        "tags": ["trachea", "airway", "bronchi", "respiratory", "CT", "windpipe", "3D shape", "thorax", "anatomy"],
        "datasets": ["SegTHOR", "TotalSegmentator"],
        "pathological_variants": ["tracheal stenosis"],
    },

    # ── ABDOMINAL ORGANS ──────────────────────────────────────────────────
    {
        "name": "Liver",
        "search_key": "liver",
        "anatomy_type": "organ",
        "body_system": "digestive",
        "description": "3D shape of the liver from abdominal CT. The largest internal organ. Includes both healthy and tumor-bearing livers from LiTS and FLARE datasets.",
        "tags": ["liver", "organ", "digestive", "CT", "abdomen", "tumor", "hepatic", "3D shape", "anatomy"],
        "datasets": ["LiTS", "FLARE", "CT-ORG", "CHAOS", "TotalSegmentator", "MSD"],
        "pathological_variants": ["liver tumor", "hepatocellular carcinoma", "liver metastasis"],
    },
    {
        "name": "Liver Tumor",
        "search_key": "liver tumor",
        "anatomy_type": "tumor",
        "body_system": "oncology",
        "description": "3D shapes of liver tumors from LiTS dataset. Includes hepatocellular carcinoma and liver metastases from CT scans with manual expert segmentations.",
        "tags": ["liver tumor", "hepatocellular carcinoma", "metastasis", "cancer", "CT", "oncology", "3D shape", "LiTS"],
        "datasets": ["LiTS", "MSD"],
        "pathological_variants": ["hepatocellular carcinoma", "cholangiocarcinoma", "liver metastasis"],
    },
    {
        "name": "Spleen",
        "search_key": "spleen",
        "anatomy_type": "organ",
        "body_system": "immune",
        "description": "3D shape of the spleen from abdominal CT. Important lymphoid organ involved in blood filtration and immune response. Used in trauma surgery planning and splenomegaly assessment.",
        "tags": ["spleen", "organ", "immune", "lymphoid", "CT", "abdomen", "trauma", "3D shape", "anatomy"],
        "datasets": ["FLARE", "CT-ORG", "CHAOS", "TotalSegmentator"],
        "pathological_variants": ["splenomegaly", "splenic cyst"],
    },
    {
        "name": "Pancreas",
        "search_key": "pancreas",
        "anatomy_type": "organ",
        "body_system": "digestive",
        "description": "3D shape of the pancreas from abdominal CT. Challenging organ to segment due to its irregular shape and low CT contrast. Used for pancreatitis and pancreatic cancer analysis.",
        "tags": ["pancreas", "organ", "digestive", "CT", "abdomen", "cancer", "diabetes", "3D shape", "anatomy"],
        "datasets": ["FLARE", "MSD", "TotalSegmentator"],
        "pathological_variants": ["pancreatic cancer", "pancreatitis"],
    },
    {
        "name": "Kidney",
        "search_key": "kidney",
        "anatomy_type": "organ",
        "body_system": "urinary",
        "description": "3D shape of the kidneys (left and right) from CT. Includes healthy kidneys and kidneys with tumors (KiTS21 dataset). Used for surgical planning, transplant evaluation, and cancer detection.",
        "tags": ["kidney", "organ", "urinary", "CT", "abdomen", "transplant", "tumor", "renal", "3D shape", "anatomy"],
        "datasets": ["KiTS21", "FLARE", "CT-ORG", "CHAOS", "TotalSegmentator"],
        "pathological_variants": ["kidney tumor", "renal cell carcinoma", "kidney cyst"],
    },
    {
        "name": "Kidney Tumor",
        "search_key": "kidney tumor",
        "anatomy_type": "tumor",
        "body_system": "oncology",
        "description": "3D shapes of kidney tumors from KiTS21 dataset. Includes renal cell carcinoma and kidney cysts with expert segmentations. Used for automated tumor staging.",
        "tags": ["kidney tumor", "renal cell carcinoma", "tumor", "cancer", "CT", "KiTS21", "oncology", "3D shape"],
        "datasets": ["KiTS21"],
        "pathological_variants": ["clear cell RCC", "papillary RCC", "oncocytoma"],
    },
    {
        "name": "Gallbladder",
        "search_key": "gallbladder",
        "anatomy_type": "organ",
        "body_system": "digestive",
        "description": "3D shape of the gallbladder from abdominal CT. Small pear-shaped organ that stores bile. Used in cholecystectomy planning and gallstone analysis.",
        "tags": ["gallbladder", "organ", "digestive", "CT", "bile", "gallstone", "cholecystectomy", "3D shape", "anatomy"],
        "datasets": ["FLARE", "TotalSegmentator"],
        "pathological_variants": ["gallstone", "cholecystitis"],
    },
    {
        "name": "Esophagus",
        "search_key": "esophagus",
        "anatomy_type": "organ",
        "body_system": "digestive",
        "description": "3D shape of the esophagus from CT. Muscular tube connecting throat to stomach. Used in esophageal cancer detection and radiotherapy planning.",
        "tags": ["esophagus", "organ", "digestive", "CT", "cancer", "radiotherapy", "thorax", "3D shape", "anatomy"],
        "datasets": ["SegTHOR", "FLARE", "TotalSegmentator"],
        "pathological_variants": ["esophageal cancer", "achalasia"],
    },
    {
        "name": "Stomach",
        "search_key": "stomach",
        "anatomy_type": "organ",
        "body_system": "digestive",
        "description": "3D shape of the stomach from abdominal CT. Highly variable shape organ used for gastric cancer analysis and surgical planning.",
        "tags": ["stomach", "organ", "digestive", "CT", "abdomen", "gastric cancer", "surgery", "3D shape", "anatomy"],
        "datasets": ["FLARE", "TotalSegmentator"],
        "pathological_variants": ["gastric cancer", "gastric ulcer"],
    },
    {
        "name": "Duodenum",
        "search_key": "duodenum",
        "anatomy_type": "organ",
        "body_system": "digestive",
        "description": "3D shape of the duodenum — the first section of the small intestine. Used in pancreatic surgery planning and digestive system modeling.",
        "tags": ["duodenum", "intestine", "digestive", "CT", "abdomen", "pancreas", "3D shape", "anatomy"],
        "datasets": ["FLARE", "TotalSegmentator"],
        "pathological_variants": ["duodenal ulcer"],
    },
    {
        "name": "Adrenal Gland",
        "search_key": "adrenal gland",
        "anatomy_type": "organ",
        "body_system": "endocrine",
        "description": "3D shapes of left and right adrenal glands from CT. Small endocrine glands sitting atop the kidneys, producing adrenaline and cortisol.",
        "tags": ["adrenal gland", "endocrine", "hormone", "CT", "kidney", "cortisol", "adrenaline", "3D shape", "anatomy"],
        "datasets": ["FLARE", "TotalSegmentator"],
        "pathological_variants": ["adrenal adenoma", "pheochromocytoma"],
    },
    {
        "name": "Inferior Vena Cava",
        "search_key": "inferior vena cava",
        "anatomy_type": "vessel",
        "body_system": "cardiovascular",
        "description": "3D shape of the inferior vena cava (IVC) — the large vein returning blood from the lower body to the heart. Used in vascular surgery and interventional radiology planning.",
        "tags": ["inferior vena cava", "IVC", "vein", "vessel", "cardiovascular", "CT", "vascular surgery", "3D shape"],
        "datasets": ["FLARE", "TotalSegmentator"],
        "pathological_variants": ["IVC thrombosis", "IVC filter"],
    },

    # ── MUSCULOSKELETAL — SPINE ───────────────────────────────────────────
    {
        "name": "Vertebrae / Spine",
        "search_key": "vertebra",
        "anatomy_type": "bone",
        "body_system": "musculoskeletal",
        "description": "3D shapes of individual vertebrae (C1–L5, sacrum) from VerSe dataset. Over 3000 annotated vertebrae from CT scans. Used for spine surgery planning, fracture detection, and scoliosis analysis.",
        "tags": ["vertebra", "spine", "bone", "CT", "fracture", "scoliosis", "lumbar", "cervical", "thoracic", "3D shape"],
        "datasets": ["VerSe", "TotalSegmentator"],
        "pathological_variants": ["vertebral fracture", "scoliosis", "spinal stenosis"],
    },
    {
        "name": "Rib",
        "search_key": "rib",
        "anatomy_type": "bone",
        "body_system": "musculoskeletal",
        "description": "3D shapes of individual ribs (1–12, left and right) from CT. Used for rib fracture detection, chest wall reconstruction, and thoracic surgery planning.",
        "tags": ["rib", "bone", "chest", "CT", "fracture", "thorax", "surgery", "3D shape", "anatomy"],
        "datasets": ["TotalSegmentator"],
        "pathological_variants": ["rib fracture"],
    },
    {
        "name": "Hip / Pelvis",
        "search_key": "hip",
        "anatomy_type": "bone",
        "body_system": "musculoskeletal",
        "description": "3D shape of the hip and pelvis bones including ilium, ischium, and pubis. Used for hip replacement planning, pelvic fracture analysis, and biomechanical modeling.",
        "tags": ["hip", "pelvis", "bone", "CT", "replacement", "fracture", "biomechanics", "orthopedics", "3D shape"],
        "datasets": ["TotalSegmentator"],
        "pathological_variants": ["hip fracture", "osteoarthritis", "dysplasia"],
    },
    {
        "name": "Femur",
        "search_key": "femur",
        "anatomy_type": "bone",
        "body_system": "musculoskeletal",
        "description": "3D shape of the femur (thigh bone) — the longest and strongest bone in the body. Used for knee/hip implant design, fracture fixation planning, and gait analysis.",
        "tags": ["femur", "thigh bone", "bone", "CT", "knee", "hip", "implant", "fracture", "orthopedics", "3D shape"],
        "datasets": ["TotalSegmentator"],
        "pathological_variants": ["femoral fracture", "avascular necrosis"],
    },

    # ── MUSCLES ───────────────────────────────────────────────────────────
    {
        "name": "Muscle (Whole Body)",
        "search_key": "muscle",
        "anatomy_type": "muscle",
        "body_system": "musculoskeletal",
        "description": "3D shapes of major muscle groups from whole-body CT/PET-CT segmentations including psoas, quadriceps, gluteus, and paraspinal muscles. Used for body composition analysis and sarcopenia assessment.",
        "tags": ["muscle", "musculoskeletal", "CT", "body composition", "sarcopenia", "psoas", "quadriceps", "3D shape"],
        "datasets": ["TotalSegmentator", "DigitalBodyPreservation"],
        "pathological_variants": ["sarcopenia", "muscle atrophy"],
    },

    # ── SURGICAL INSTRUMENTS ──────────────────────────────────────────────
    {
        "name": "Surgical Instrument",
        "search_key": "surgical instrument",
        "anatomy_type": "surgical_instrument",
        "body_system": "medical_device",
        "description": "3D models of surgical instruments including forceps, scissors, needles, and endoscopic tools. Used for robot-assisted surgery simulation, AR surgical training, and instrument tracking.",
        "tags": ["surgical instrument", "forceps", "scissors", "endoscope", "robot surgery", "laparoscopy", "AR", "3D model", "medical device"],
        "datasets": ["SurgicalInstruments"],
        "pathological_variants": [],
    },

    # ── WHOLE BODY ────────────────────────────────────────────────────────
    {
        "name": "Whole Body Anatomy",
        "search_key": "whole body",
        "anatomy_type": "whole_body",
        "body_system": "musculoskeletal",
        "description": "Complete whole-body 3D anatomical models from TotalSegmentator and DigitalBodyPreservation datasets, including all major organs, bones, muscles, and vessels dissembled and labeled. Used for medical education, XR anatomy visualization, and body composition analysis.",
        "tags": ["whole body", "anatomy", "CT", "total segmentator", "education", "XR", "VR", "3D shape", "body composition"],
        "datasets": ["TotalSegmentator", "DigitalBodyPreservation"],
        "pathological_variants": [],
    },
]

# ---------------------------------------------------------------------------
# BUILD METADATA
# ---------------------------------------------------------------------------
def build_metadata() -> list[dict]:
    entries = []

    # 1. Dataset-level entries (23 sub-datasets)
    for ds in DATASETS:
        entry = {
            "id":             f"msn_dataset_{ds['dataset_key'].lower().replace('-','_').replace(' ','_')}",
            "name":           ds["dataset_name"],
            "search_key":     ds["dataset_key"],
            "category":       "dataset",
            "anatomy_types":  ds["anatomy_types"],
            "body_systems":   ds["body_systems"],
            "description":    f"{ds['dataset_name']} — a MedShapeNet sub-dataset containing {ds['shape_count']} 3D medical shapes of type: {', '.join(ds['anatomy_types'])}.",
            "tags":           ds["anatomy_types"] + ds["body_systems"] + ["MedShapeNet", "3D shape", "medical", "anatomy"],
            "shape_count":    ds["shape_count"],
            "source":         "MedShapeNet",
            "source_type":    "medical_shape_database",
            "render_type":    "mesh_viewer",
            "shape_formats":  ["STL", "NIfTI", "PLY"],
            "embed_url":      "https://medshapenet.ikim.nrw/",
            "fetch_method":   "msn_api",
            "fetch_code":     f"from MedShapeNet import MedShapeNet; msn = MedShapeNet(); msn.search_and_download_by_name('{ds['dataset_key']}', output_dir='./cache/')",
            "local_file":     None,
            "runtime_fetch":  True,
            "license":        ds["license"],
            "pathological_variants": [],
        }
        entries.append(entry)

    # 2. Anatomy-level entries (individual shape types)
    for anat in ANATOMIES:
        entry = {
            "id":             f"msn_anatomy_{anat['search_key'].replace(' ', '_').replace('/','_')}",
            "name":           anat["name"],
            "search_key":     anat["search_key"],
            "category":       "anatomy",
            "anatomy_type":   anat["anatomy_type"],
            "body_system":    anat["body_system"],
            "description":    anat["description"],
            "tags":           anat["tags"],
            "datasets":       anat["datasets"],
            "pathological_variants": anat.get("pathological_variants", []),
            "source":         "MedShapeNet",
            "source_type":    "medical_shape_database",
            "render_type":    "mesh_viewer",
            "shape_formats":  ["STL", "NIfTI", "PLY"],
            "embed_url":      "https://medshapenet.ikim.nrw/",
            "fetch_method":   "msn_api",
            "fetch_code":     f"from MedShapeNet import MedShapeNet; msn = MedShapeNet(); msn.search_and_download_by_name('{anat['search_key']}', output_dir='./cache/')",
            "local_file":     None,
            "runtime_fetch":  True,
            "license":        "CC BY 4.0 (varies by sub-dataset)",
        }
        entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    metadata = build_metadata()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"  MedShapeNet Metadata")
    print(f"{'='*60}")
    print(f"  Total entries:       {len(metadata)}")
    print(f"  Dataset entries:     {sum(1 for e in metadata if e['category'] == 'dataset')}")
    print(f"  Anatomy entries:     {sum(1 for e in metadata if e['category'] == 'anatomy')}")
    print(f"\n  By body system:")
    systems = Counter()
    for e in metadata:
        if e["category"] == "anatomy":
            systems[e["body_system"]] += 1
    for sys, count in sorted(systems.items(), key=lambda x: -x[1]):
        print(f"    {sys:<25} {count}")
    print(f"\n  ✅ Written → {OUTPUT_FILE}")
    print(f"""
  RUNTIME FETCH:
    pip install MedShapeNet
    from MedShapeNet import MedShapeNet
    msn = MedShapeNet()
    msn.search_and_download_by_name("liver", output_dir="./cache/")

  RENDERING (STL/PLY files):
    Three.js STLLoader:
      import {{ STLLoader }} from 'three/examples/jsm/loaders/STLLoader'
      const loader = new STLLoader()
      loader.load('./cache/liver.stl', geometry => {{
        const mesh = new THREE.Mesh(geometry, material)
        scene.add(mesh)
      }})
{'='*60}
""")
