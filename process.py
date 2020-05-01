#!/usr/bin/env python

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from audio_denoising.data.loader import SpectogramDataset
from audio_denoising.model.rdn import ResidualDenseNetwork as Model

SOURCE_DIR = os.environ["SOURCE_DIR"] if "SOURCE_DIR" in os.environ else "/dataset"
TARGET_DIR = os.environ["TARGET_DIR"] if "TARGET_DIR" in os.environ else "/results"


def process(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = Model(args).to(device)
    model.load_state_dict(torch.load(args.weights, map_location=device))
    model.eval()

    dataset = SpectogramDataset(args.source_dir, extension=args.extension)

    files = dataset.files

    filenames = []
    results = []
    denoised_filenames = []

    for file_idx in tqdm(range(len(dataset)), unit="files"):
        filename = files[file_idx]
        filenames.append(filename)

        img = dataset[file_idx].unsqueeze(0)
        img = img.to(device, dtype=torch.float)
        noise = model(img)
        print(torch.nn.functional.mse_loss(torch.zeros_like(noise), noise))
        if torch.allclose(torch.zeros_like(noise), noise, atol=args.threshold):
            results.append("clean")
            denoised_filenames.append("")
        else:
            results.append("noisy")

            denoised_filename = Path(args.target_dir) / (
                args.denoised_subdir + filename.split(str(Path(args.source_dir)))[1]
            )
            Path.mkdir(denoised_filename.parent, exist_ok=True, parents=True)
            denoised_filenames.append(str(denoised_filename))

            clean_img = img - noise

            np.save(denoised_filename, clean_img.to("cpu").detach().numpy())

    results_df = pd.DataFrame(
        {"file_name": filenames, "result": results, "denoised_file": denoised_filenames}
    )

    results_df.to_csv(Path(args.target_dir) / "results.csv", index=False)

    return results_df


def get_arg_parser():
    parser = argparse.ArgumentParser()

    # model
    parser.add_argument("--growth-rate", type=int, default=24)
    parser.add_argument("--kernel-size", type=int, default=3)
    parser.add_argument("--num-blocks", type=int, default=9)
    parser.add_argument("--num-channels", type=int, default=1)
    parser.add_argument("--num-features", type=int, default=16)
    parser.add_argument("--num-layers", type=int, default=6)

    # setup
    parser.add_argument(
        "--source-dir", type=str, default=SOURCE_DIR,
    )
    parser.add_argument(
        "--target-dir", type=str, default=TARGET_DIR,
    )

    parser.add_argument(
        "--denoised-subdir", type=str, default="denoised",
    )
    parser.add_argument(
        "--extension", type=str, default="npy",
    )

    parser.add_argument(
        "--weights",
        type=str,
        default="./weights/audio_denoising_psnr_59.7472_epoch_6.pth",
    )

    parser.add_argument(
        "--threshold", type=float, default=5e-3,
    )

    return parser


if __name__ == "__main__":
    args = get_arg_parser().parse_args()
    print("*" * 80)
    print(
        "Starting to process the {} files in the '{}' directory".format(
            args.extension, args.source_dir
        )
    )
    print("*" * 80)
    print("Args")
    print("-" * 80)
    for key, value in vars(args).items():
        print("\t{}:\t{}".format(key, value))
    print("*" * 80)
    process(args)
    print("*" * 80)
    print("Done!")
