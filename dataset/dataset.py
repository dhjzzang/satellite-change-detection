from typing import List, Tuple
from collections import Sized
from os.path import join
import albumentations as alb
from torchvision.transforms import Normalize, Compose, ToTensor, Resize, ToPILImage, CenterCrop
from torchvision import transforms
import numpy as np
import torch
from matplotlib import image as mimg
from matplotlib.image import imread
from torch.utils.data import Dataset
from torch import Tensor
from PIL import Image

class MyDataset(Dataset, Sized):
    def __init__(
        self,
        data_path: str,
        mode: str,
    ) -> None:
        """
        data_path: Folder containing the sub-folders:
            "A" for test images,
            "B" for ref images, 
            "label" for the gt masks,
            "list" containing the image list files ("train.txt", "test.txt", "eval.txt").
        """
        # Store the path data path + mode (train,val,test):
        self._mode = mode
        self._A = join(data_path,self._mode ,"A")
        self._B = join(data_path,self._mode, "B")
        self._label = join(data_path,self._mode, "label")

        # In all the dirs, the files share the same names:
        self._list_images = self._read_images_list(data_path)

        # Initialize augmentations:
        if mode == 'train':
            self._augmentation = _create_shared_augmentation()
            self._aberration = _create_aberration_augmentation()
        
        # Initialize normalization:
        self._normalize = Normalize(mean=[0.485, 0.456, 0.406],
                                 std=[0.229, 0.224, 0.225])
        
        self._preprocess = Compose([CenterCrop(256),
                                    self._normalize])
        
        self._preprocess_mask = Compose([CenterCrop(256)
                                    ])
        
        
    def __getitem__(self, indx):
        # Current image set name:
        img_name = self._list_images[indx].strip('\n')
        # Loading the images:
        x_ref = imread(join(self._A, img_name))
        x_test = imread(join(self._B, img_name))
        x_mask = _binarize(imread(join(self._label, img_name)))

        if self._mode == "train":
            x_ref, x_test, x_mask = self._augment(x_ref, x_test, x_mask)

        x_ref, x_test, x_mask = self._to_tensors(x_ref, x_test, x_mask)

        return (x_ref, x_test), x_mask, img_name

    def __len__(self):
        return len(self._list_images)

    def _read_images_list(self, data_path: str) -> List[str]:
        images_list_file = join(data_path,'list', self._mode + ".txt")
        with open(images_list_file, "r") as f:
            return f.readlines()
    
    def _augment(
        self, x_ref: np.ndarray, x_test: np.ndarray, x_mask: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        # First apply augmentations in equal manner to test/ref/x_mask:
        transformed = self._augmentation(image=x_ref, image0=x_test, x_mask0=x_mask)
        x_ref = transformed["image"]
        x_test = transformed["image0"]
        x_mask = transformed["x_mask0"]

        # Then apply augmentation to single test ref in different way:
        x_ref = self._aberration(image=x_ref)["image"]
        x_test = self._aberration(image=x_test)["image"]

        return x_ref, x_test, x_mask
    
    def _to_tensors(
        self, x_ref: np.ndarray, x_test: np.ndarray, x_mask: np.ndarray
    ) -> Tuple[Tensor, Tensor, Tensor]:

        x_ref = self._preprocess(torch.tensor(x_ref).permute(2, 0, 1))
        x_test = self._preprocess(torch.tensor(x_test).permute(2, 0, 1))
        x_mask = self._preprocess_mask(torch.tensor(x_mask))
        return (
            x_ref,
            x_test,
            x_mask
        )

def _create_shared_augmentation():
    return alb.Compose(
        [
            alb.Flip(p=0.5),
            alb.Rotate(limit=5, p=0.5),
        ],
        additional_targets={"image0": "image", "x_mask0": "mask"},
        is_check_shapes=False,
    )


def _create_aberration_augmentation():
    return alb.Compose([
        alb.RandomBrightnessContrast(
            brightness_limit=0.2, contrast_limit=0.2, p=0.5
        ),
        alb.GaussianBlur(blur_limit=[3, 5], p=0.5),
    ])

def _binarize(mask: np.ndarray) -> np.ndarray:
    return np.clip(mask * 255, 0, 1).astype(int)