#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP Vision Service — Configuration
Model paths, device settings, and constants.
"""

import os
import torch

# ============================================================
# Paths
# ============================================================
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SERVICE_DIR)  # torchxrayvision root

# Model weights — loaded from local models/ folder
YOLO_WEIGHTS = os.path.join(SERVICE_DIR, "models", "best.pt")
MEDSAM_CHECKPOINT = os.path.join(SERVICE_DIR, "models", "MedSAM2_latest.pt")

# Output directory
OUTPUT_DIR = os.path.join(SERVICE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# Device
# ============================================================
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ============================================================
# Constants
# ============================================================
SOLID_LESIONS = {'Nodule_Mass', 'Calcification'}
CARDIAC_LESIONS = {'Cardiomegaly', 'Aortic_enlargement', 'Aortic enlargement'}
PLEURAL_LESIONS = {'Pleural_effusion', 'Pleural effusion', 'Pneumothorax',
                   'Pleural_thickening', 'Pleural thickening'}

MERGE_IOU_THRESHOLD = 0.50

PATHOLOGY_CN = {
    'Atelectasis': '肺不张', 'Consolidation': '实变',
    'Infiltration': '浸润', 'Pneumothorax': '气胸',
    'Edema': '水肿', 'Emphysema': '肺气肿',
    'Fibrosis': '纤维化', 'Effusion': '胸腔积液',
    'Pneumonia': '肺炎', 'Pleural_Thickening': '胸膜增厚',
    'Cardiomegaly': '心脏扩大', 'Nodule': '结节',
    'Mass': '肿块', 'Hernia': '疝气',
    'Lung Lesion': '肺部病变', 'Fracture': '骨折',
    'Lung Opacity': '肺部阴影', 'Enlarged Cardiomediastinum': '心纵隔增大'
}

FINDING_COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c']
