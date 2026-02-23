#!/usr/bin/env python3
import numpy as np
import matplotlib.pyplot as plt
import argparse
import os
import json
from pathlib import Path

def create_radar_chart(npy_path, metadata_path=None, num_bins=32):
    # 1. Загрузка данных
    if not os.path.exists(npy_path):
        print(f"Ошибка: Файл {npy_path} не найден")
        return

    embedding = np.load(npy_path)
    speaker_id = Path(npy_path).stem
    
    # Пытаемся достать имя
    display_name = speaker_id
    if metadata_path and os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r') as f:
                meta = json.load(f)
                display_name = meta.get(speaker_id, {}).get('name', speaker_id)
        except Exception: pass

    # 2. Обработка данных
    # Делим на чанки. Если 512 не делится на num_bins ровно, np.array_split это отработает.
    chunks = np.array_split(embedding, num_bins)
    
    # Считаем "мощность" каждого сектора (RMS - Root Mean Square)
    # Это сделает график более выразительным, чем просто среднее
    data_binned = np.array([np.sqrt(np.mean(np.square(chunk))) for chunk in chunks])
    
    # Проверка: если все значения мизерные, выведем инфо
    print(f"Stats for {speaker_id}: Max={data_binned.max():.4f}, Mean={data_binned.mean():.4f}")

    # Замыкаем круг
    angles = np.linspace(0, 2*np.pi, num_bins, endpoint=False).tolist()
    data_plot = np.concatenate((data_binned, [data_binned[0]]))
    angles += [angles[0]]

    # 3. Построение
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    
    # Рисуем "тело" графика
    ax.fill(angles, data_plot, color='#1f77b4', alpha=0.3)
    ax.plot(angles, data_plot, color='#1f77b4', linewidth=2.5, marker='o', markersize=4, markevery=1)

    # Настройка сетки
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    
    # Динамический предел с запасом, чтобы график не упирался в края
    ax.set_ylim(0, max(data_binned.max() * 1.2, 0.05)) 

    # Подписи
    ax.set_xticks(np.linspace(0, 2*np.pi, 8, endpoint=False))
    ax.set_xticklabels([f"V{i*num_bins//8}" for i in range(8)], color='gray')
    
    plt.title(f"Voice Signature: {display_name}\nID: {speaker_id}", size=15, pad=30)

    # 4. Сохранение
    out_dir = "speakers/visuals"
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{speaker_id}_radar.png")
    
    # Важно: используем tight_layout, чтобы заголовки не обрезались
    plt.tight_layout()
    plt.savefig(out_file, dpi=120)
    plt.close()
    
    print(f"✓ Готово: {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    args = parser.parse_args()
    create_radar_chart(args.input)