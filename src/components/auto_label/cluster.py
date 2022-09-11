from glob import glob
import os
import shutil
import sys
from typing import List
from loguru import logger
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

from .base import BaseLabeler
from .emb import *
from .img2emb import Img2Emb
from components.utils import ToolBox


class ClusterLabeler(BaseLabeler):
    def __init__(
        self,
        data_dir,
        num_class: int = 2,
        labels: List[str] = None,
        num_feat: int = 128,
        model: str = "resnet-18",
        layer: str = "default",
        layer_output_size: int = 512,
        save: bool = False,
    ) -> None:
        super().__init__(data_dir, num_class, labels)
        self.img2emb = Img2Emb(
            model=model,
            layer=layer,
            layer_output_size=layer_output_size,
            save=save,
        )
        self.num_feat = num_feat
        self._dir_unlabel = os.path.join(self.data_dir, "unlabel")

        if not os.path.exists(self._dir_unlabel):
            raise ValueError(
                f"Unlabelled directory not found: {self._dir_unlabel}, please run `scaffold new` first"
            )

        self.images = []
        self.embs = []

    def run(self):
        self.images = []
        for ext in ToolBox.IMAGE_EXT:
            self.images.extend(
                glob(os.path.join(self._dir_unlabel, f"**/*.{ext}"), recursive=True)
            )
        self.images = sorted(self.images)

        if len(self.images) == 0:
            raise ValueError(f"No images found in {self._dir_unlabel}")

        logger.info(f"Found {len(self.images)} images in {self._dir_unlabel}")
        logger.debug("Extracting embeddings...")
        for i, img in enumerate(self.images):
            img = Image.open(img)
            emb = self.img2emb.get_emb(img)
            self.embs.append(emb)
            if (i + 1) % 100 == 0:
                logger.debug(f"Extracted {(i+1)} embeddings")
        logger.debug("Embeddings extracted")

        self.embs = np.array(self.embs)
        logger.debug("PCA..., shape of embs: {}".format(self.embs.shape))
        self.embs = PCA(n_components=self.num_feat).fit_transform(self.embs)
        logger.debug("PCA done, shape of embs: {}".format(self.embs.shape))

        logger.debug("Clustering...")
        kmeans = KMeans(n_clusters=self.num_class).fit(self.embs)
        logger.debug("Clustering done")

        labels_ = np.array(kmeans.labels_)
        logger.debug("Saving labels...")
        for i, label in enumerate(labels_):
            label = self.labels[label]
            img = self.images[i]
            img_name = os.path.basename(img)
            label_path = os.path.join(self.data_dir, label)
            if not os.path.exists(label_path):
                os.makedirs(label_path)
            shutil.copy(img, os.path.join(label_path, img_name))
        logger.debug("Labels saved")
