import logging

from tqdm import tqdm
import numpy as np
import torch

from fnet.data.fnetdataset import FnetDataset


logger = logging.getLogger(__name__)


class BufferedPatchDataset(FnetDataset):
    """Dataset that provides chunks/patchs from another dataset."""

    def __init__(
        self,
        dataset,
        patch_size=(32, 64, 64),
        buffer_size=1,
        buffer_switch_frequency=-1,
        npatches=100000,
        verbose=False,
        shuffle_images=True,
        dim_squeeze=None,
    ):
        self.counter = 0
        self.dataset = dataset
        self.buffer_size = min(len(self.dataset), buffer_size)
        self.buffer_switch_frequency = buffer_switch_frequency
        self.npatches = npatches
        self.buffer = list()
        self.verbose = verbose
        self.shuffle_images = shuffle_images
        self.dim_squeeze = dim_squeeze
        shuffed_data_order = np.arange(0, len(dataset))
        if self.shuffle_images:
            np.random.shuffle(shuffed_data_order)
        pbar = tqdm(range(0, self.buffer_size))
        self.buffer_history = list()
        for i in pbar:
            # convert from a torch.Size object to a list
            if self.verbose:
                pbar.set_description("buffering images")
            datum_index = shuffed_data_order[i]
            datum = dataset[datum_index]
            datum_size = datum[0].size()
            self.buffer_history.append(datum_index)
            self.buffer.append(datum)
        self.remaining_to_be_in_buffer = shuffed_data_order[i + 1:]
        assert len(patch_size) + 1 == len(datum_size)
        self.patch_size = [datum_size[0]] + list(patch_size)

    def __len__(self):
        return self.npatches

    def __getitem__(self, index):
        self.counter += 1
        if (self.buffer_switch_frequency > 0) and (
            self.counter % self.buffer_switch_frequency == 0
        ):
            if self.verbose:
                logger.info("Inserting new item into buffer")
            self.insert_new_element_into_buffer()
        return self.get_random_patch()

    def insert_new_element_into_buffer(self):
        # sample with replacement
        self.buffer.pop(0)
        if self.shuffle_images:

            if len(self.remaining_to_be_in_buffer) == 0:
                self.remaining_to_be_in_buffer = np.arange(
                    0, len(self.dataset)
                )
                np.random.shuffle(self.remaining_to_be_in_buffer)

            new_datum_index = self.remaining_to_be_in_buffer[0]
            self.remaining_to_be_in_buffer = self.remaining_to_be_in_buffer[1:]

        else:
            new_datum_index = self.buffer_history[-1] + 1
            if new_datum_index == len(self.dataset):
                new_datum_index = 0

        self.buffer_history.append(new_datum_index)
        self.buffer.append(self.dataset[new_datum_index])

        if self.verbose:
            logger.info(f"Added item {new_datum_index}")

    def get_random_patch(self):
        buffer_index = np.random.randint(len(self.buffer))
        datum = self.buffer[buffer_index]
        starts = np.array(
            [
                np.random.randint(0, d - p + 1) if d - p + 1 >= 1 else 0
                for d, p in zip(datum[0].size(), self.patch_size)
            ]
        )
        ends = starts + np.array(self.patch_size)
        # thank you Rory for this weird trick
        index = [slice(s, e) for s, e in zip(starts, ends)]
        patch = [d[tuple(index)] for d in datum]
        if self.dim_squeeze is not None:
            patch = [torch.squeeze(d, self.dim_squeeze) for d in patch]
        return patch

    def get_buffer_history(self):
        return self.buffer_history
