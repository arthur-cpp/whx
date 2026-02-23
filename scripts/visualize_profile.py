#!/usr/bin/env python3
import numpy as np
import matplotlib.pyplot as plt
import argparse
import json
import os
from pathlib import Path

def generate_voice_print(npy_path, metadata_path=None, output_dir="speakers/visuals"):
    # 1. Загрузка данных
    embedding = np.load(npy_path)
    speaker_id = Path(npy_path).stem
    
    # Пытаемся достать красивое имя из метаданных
    display_name = speaker_id
    if metadata_path and os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            meta = json.load(f)
            if speaker_id in meta:
                display_name = meta[speaker_id].get('name', speaker_id)

    # 2. Подготовка матрицы
    # 512 элементов идеально ложатся в сетку 16x32
    grid = embedding.reshape((16, 32))

    # 3. Визуализация
    plt.figure(figsize=(10, 6))
    
    # Используем симметричную палитру RdBu_r (Red-Blue reversed)
    # vmin/vmax фиксированы, чтобы цвета были сопоставимы между разными файлами
    v_limit = max(abs(embedding.min()), abs(embedding.max()), 0.15)
    im = plt.imshow(grid, cmap='RdBu_r', aspect='equal', 
                    vmin=-v_limit, vmax=v_limit, interpolation='nearest')
    
    plt.colorbar(im, label='Feature Intensity')
    plt.title(f"Voice Print: {display_name}\nID: {speaker_id}", fontsize=14, pad=15)
    
    # Убираем оси для "чистого" вида или оставляем сетку для сравнения
    plt.xticks(np.arange(-.5, 32, 1), [])
    plt.yticks(np.arange(-.5, 16, 1), [])
    plt.grid(color='white', linestyle='-', linewidth=0.5, alpha=0.3)

    # 4. Сохранение
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"{speaker_id}_print.png")
    plt.savefig(out_file, bbox_inches='tight', dpi=150)
    plt.close()
    
    print(f"✓ Visual fingerprint saved to: {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a visual fingerprint from a speaker .npy profile")
    parser.add_argument("input", help="Path to the .npy profile")
    parser.add_argument("--metadata", default="speakers/data/speakers.json", help="Path to speakers.json")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: File {args.input} not found")
    else:
        generate_voice_print(args.input, args.metadata)