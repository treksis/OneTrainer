import os
from typing import Optional, Tuple

import numpy as np
import onnxruntime
import pooch
import torch
from PIL import Image
from numpy import ndarray
from torch import Tensor, nn
from torchvision.transforms import functional, transforms

from modules.module.BaseImageMaskModel import BaseImageMaskModel, MaskSample


class RembgModel(BaseImageMaskModel):
    def __init__(self, device: torch.device, dtype: torch.dtype):
        self.device = device
        self.dtype = dtype

        self.model = self.__load_model()

        self.smoothing_kernel_radius = None
        self.smoothing_kernel = self.__create_average_kernel(self.smoothing_kernel_radius)

        self.expand_kernel_radius = None
        self.expand_kernel = self.__create_average_kernel(self.expand_kernel_radius)

        self.image2Tensor = transforms.Compose([
            transforms.ToTensor(),
        ])

    def __load_model(self) -> onnxruntime.InferenceSession:
        filename = "u2net.onnx"
        path = os.path.join("external", "models", "rembg")

        pooch.retrieve(
            "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx",
            "md5:60024c5c889badc19c04ad937298a77b",
            fname=filename,
            path=path,
            progressbar=True,
        )

        return onnxruntime.InferenceSession(os.path.join(path, filename))

    def __create_average_kernel(self, kernel_radius: Optional[int]):
        if kernel_radius is None:
            return None

        kernel_size = kernel_radius * 2 + 1
        kernel_weights = torch.ones(1, 1, kernel_size, kernel_size) / (kernel_size * kernel_size)
        kernel = nn.Conv2d(
            in_channels=1, out_channels=1, kernel_size=kernel_size, bias=False, padding_mode='replicate',
            padding=kernel_radius
        )
        kernel.weight.data = kernel_weights
        kernel.requires_grad_(False)
        kernel.to(self.device)
        return kernel

    def __process_mask(self, mask: Tensor, target_height: int, target_width: int, threshold: float) -> Tensor:
        while len(mask.shape) < 4:
            mask = mask.unsqueeze(0)

        mask = mask.mean(1).unsqueeze(1)
        if self.smoothing_kernel is not None:
            mask = self.smoothing_kernel(mask)
        mask = functional.resize(mask, [target_height, target_width])
        mask = (mask > threshold).float()
        if self.expand_kernel is not None:
            mask = self.expand_kernel(mask)
        mask = (mask > 0).float()

        return mask

    def __normalize(
            self,
            img: Image.Image,
            mean: Tuple[float, float, float],
            std: Tuple[float, float, float],
            size: Tuple[int, int],
    ) -> ndarray:
        im = img.resize(size, Image.LANCZOS)

        im_ary = np.array(im)
        im_ary = im_ary / np.max(im_ary)

        tmpImg = np.zeros((im_ary.shape[0], im_ary.shape[1], 3))
        tmpImg[:, :, 0] = (im_ary[:, :, 0] - mean[0]) / std[0]
        tmpImg[:, :, 1] = (im_ary[:, :, 1] - mean[1]) / std[1]
        tmpImg[:, :, 2] = (im_ary[:, :, 2] - mean[2]) / std[2]

        tmpImg = tmpImg.transpose((2, 0, 1))

        return np.expand_dims(tmpImg, 0).astype(np.float32)

    def mask_image(
            self,
            filename: str,
            prompts: [str],
            mode: str = 'fill',
            threshold: float = 0.3,
            smooth_pixels: int = 5,
            expand_pixels: int = 10
    ):
        mask_sample = MaskSample(filename, self.device)

        if mode == 'fill' and mask_sample.get_mask_tensor() is not None:
            return

        if self.smoothing_kernel_radius != smooth_pixels:
            self.smoothing_kernel = self.__create_average_kernel(smooth_pixels)
            self.smoothing_kernel_radius = smooth_pixels

        if self.expand_kernel_radius != expand_pixels:
            self.expand_kernel = self.__create_average_kernel(expand_pixels)
            self.expand_kernel_radius = expand_pixels

        image = mask_sample.get_image()

        normalized_image = self.__normalize(
            image,
            (0.485, 0.456, 0.406),
            (0.229, 0.224, 0.225),
            (320, 320)
        )

        input_name = self.model.get_inputs()[0].name
        mask = self.model.run(None, {input_name: normalized_image})

        mask = mask[0][:, 0, :, :]

        ma = np.max(mask)
        mi = np.min(mask)

        mask = (mask - mi) / (ma - mi)
        mask = np.squeeze(mask)

        output = torch.from_numpy(mask).to(self.device)

        predicted_mask = self.__process_mask(output, mask_sample.height, mask_sample.width, threshold)

        if mode == 'replace' or mode == 'fill':
            mask_sample.set_mask_tensor(predicted_mask)
        elif mode == 'add':
            mask_sample.add_mask_tensor(predicted_mask)
        elif mode == 'subtract':
            mask_sample.subtract_mask_tensor(predicted_mask)

        mask_sample.save_mask()
