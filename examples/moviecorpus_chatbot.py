import numpy as np
import torch

from ignite.metrics import Loss
from torch.utils.data import DataLoader, SubsetRandomSampler
from torchvision.transforms import Compose

from slp.util.embeddings import EmbeddingsLoader
from slp.data.moviecorpus import MovieCorpusDataset
from slp.data.transforms import SpacyTokenizer, ToTokenIds, ToTensor
from slp.data.collators import Seq2SeqCollator
from slp.trainer.trainer import Seq2SeqTrainer
from slp.config.moviecorpus import SPECIAL_TOKENS
from slp.modules.loss import SequenceCrossEntropyLoss
from slp.modules.seq2seq import EncoderDecoder, EncoderLSTM, DecoderLSTMv2

from torch.optim import Adam

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
COLLATE_FN = Seq2SeqCollator(device='cpu')
MAX_EPOCHS = 50
BATCH_TRAIN_SIZE = 32
BATCH_VAL_SIZE = 32
min_threshold = 2
max_threshold = 18
max_target_len = max_threshold


def dataloaders_from_indices(dataset, train_indices, val_indices, batch_train,
                             batch_val):
    train_sampler = SubsetRandomSampler(train_indices)
    val_sampler = SubsetRandomSampler(val_indices)

    train_loader = DataLoader(
        dataset,
        batch_size=batch_train,
        sampler=train_sampler,
        drop_last=False,
        collate_fn=COLLATE_FN)
    val_loader = DataLoader(
        dataset,
        batch_size=batch_val,
        sampler=val_sampler,
        drop_last=False,
        collate_fn=COLLATE_FN)
    return train_loader, val_loader


def train_test_split(dataset, batch_train, batch_val,
                     test_size=0.2, shuffle=True, seed=None):
    dataset_size = len(dataset)
    indices = list(range(dataset_size))
    test_split = int(np.floor(test_size * dataset_size))
    if shuffle:
        if seed is not None:
            np.random.seed(seed)
        np.random.shuffle(indices)

    train_indices = indices[test_split:]
    val_indices = indices[:test_split]
    return dataloaders_from_indices(dataset, train_indices, val_indices,
                                    batch_train, batch_val)


def trainer_factory(embeddings, pad_index, bos_index, device=DEVICE):
    encoder = EncoderLSTM(embeddings, emb_train=False, hidden_size=256,
                          num_layers=2, bidirectional=True, dropout=0.2,
                          attention=False, rnn_type='rnn', device=DEVICE)
    decoder = DecoderLSTMv2(embeddings, emb_train=False, hidden_size=256,
                            output_size=embeddings.shape[0],
                            max_target_len=max_target_len, num_layers=2,
                            dropout=0.2, rnn_type='rnn', bidirectional=False,
                            device=DEVICE)

    # encoder = Encoder_best(512,embeddings,layers=2,bidirectional=True,
    # dropout=0.2, device=DEVICE)
    # decoder = Decoder_best(512,embeddings,output_size=embeddings.shape[0],
    # max_target_len=max_target_len,layers=2,dropout=0.2,device=DEVICE)

    model = EncoderDecoder(
        encoder, decoder, bos_index, teacher_forcing_ratio=1, device=DEVICE)

    optimizer = Adam(
        [p for p in model.parameters() if p.requires_grad],
        lr=1e-3)

    criterion = SequenceCrossEntropyLoss(pad_index)

    metrics = {
        'loss': Loss(criterion)
    }

    trainer = Seq2SeqTrainer(model,
                             optimizer,
                             checkpoint_dir=None,  # '../checkpoints',
                             metrics=metrics,
                             non_blocking=True,
                             retain_graph=False,
                             patience=5,
                             device=device,
                             loss_fn=criterion)
    return trainer


if __name__ == '__main__':
    loader = EmbeddingsLoader(
        './cache/glove.6B.50d.txt', 50, extra_tokens=SPECIAL_TOKENS)
    word2idx, _, embeddings = loader.load()

    pad_index = word2idx[SPECIAL_TOKENS.PAD.value]
    bos_index = word2idx[SPECIAL_TOKENS.BOS.value]

    tokenizer = SpacyTokenizer(prepend_bos=True,
                               append_eos=True,
                               specials=SPECIAL_TOKENS)
    to_token_ids = ToTokenIds(word2idx)
    to_tensor = ToTensor(device='cpu')

    transforms = Compose([tokenizer, to_token_ids, to_tensor])
    dataset = MovieCorpusDataset('./data/', transforms=transforms)
    dataset.filter_data(min_threshold, max_threshold)

    print(len(dataset))

    train_loader, val_loader = train_test_split(dataset, BATCH_TRAIN_SIZE,
                                                BATCH_VAL_SIZE)
    trainer = trainer_factory(embeddings, pad_index, bos_index, device=DEVICE)
    final_score = trainer.fit(train_loader, val_loader, epochs=MAX_EPOCHS)

    print(f'Final score: {final_score}')
