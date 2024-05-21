from dataclasses import dataclass
import os

import torch
import torch.nn as nn
import torch.optim as optim
from torch.nn import functional as F

from typing import Optional

from model import Model
from prepare_data import preprocess_dialogues
from utils import get_tokenizer


device = 'cuda' if torch.cuda.is_available() else 'cpu'
batch_size = 8
block_size = 16
max_iters = 30000
eval_interval = 100
learning_rate = 1e-4
eval_iters = 50
dropout = 0.2
model_path = os.path.join(os.getcwd(), "model", "snapshot.pt")
model_dir = os.path.join(os.getcwd(), "model")
if not os.path.exists(model_dir):
    os.makedirs(model_dir)


@dataclass
class ModelArgs:
    block_size: int = 1024
    vocab_size: int = 32002
    n_layer: int = 1
    n_head: int = 1
    n_embd: int = 768
    dropout: float = 0.0
    bias: bool = False
    norm_eps: float = 1e-4

torch.manual_seed(42)

tokenizer = get_tokenizer()
data_path = os.getcwd() + "/data.json"

data = preprocess_dialogues(data_path, tokenizer)
data = torch.tensor(data, dtype=torch.long, device=device)
print(data.shape, data.dtype)

n = int(0.9*len(data))
train_data = data[:n]
val_data = data[n:]



def get_batch(split):
    data = train_data if split == 'train' else val_data
    ix = torch.randint(len(data) - block_size, (batch_size,))
    x = torch.stack([data[i:i+block_size] for i in ix])
    y = torch.stack([data[i+1:i+block_size+1] for i in ix])
    return x, y

model_args = ModelArgs()
model = Model(model_args)
model = model.to(device)
optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
print(sum(p.numel() for p in model.parameters())/1e6, 'M parameters')


@torch.no_grad()
def estimate_loss():
    out = {}
    model.eval()
    for split in ['train', 'val']:
        losses = torch.zeros(eval_iters)
        for k in range(eval_iters):
            X, Y = get_batch(split)
            logits, loss = model(X, Y)
            losses[k] = loss.item()
        out[split] = losses.mean()
    model.train()
    return out


for iter in range(max_iters):

    if iter % eval_interval == 0 or iter == max_iters - 1:
        losses = estimate_loss()
        print(f"step {iter}: train loss {losses['train']:.4f}, val loss {losses['val']:.4f}")

    xb, yb = get_batch('train')

    logits, loss = model(xb, yb)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    optimizer.step()


text = "<user>merhabalar<bot>"
context = torch.tensor([tokenizer.encode(text)], dtype=torch.long, device=device)
print(tokenizer.decode(model.generate(context, max_new_tokens=100)[0].tolist()))


torch.save(model.state_dict(), model_path)

