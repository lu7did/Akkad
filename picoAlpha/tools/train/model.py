"""Tiny dual-head NNUE: 780 x 16 + 16->1, 16->64, 16->64."""
from common import features,move_indices

def build_model(hidden=16):
    import torch
    from torch import nn
    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed=nn.EmbeddingBag(780,hidden,mode='sum')
            self.value=nn.Linear(hidden,1,bias=False)
            self.from_head=nn.Linear(hidden,64,bias=False)
            self.to_head=nn.Linear(hidden,64,bias=False)
            self.reset()
        def reset(self):
            nn.init.uniform_(self.embed.weight,-.02,.02)
            for head in (self.value,self.from_head,self.to_head): nn.init.uniform_(head.weight,-.02,.02)
        def forward(self,indices,offsets):
            h=self.embed(indices,offsets).relu()
            return self.from_head(h),self.to_head(h),self.value(h).tanh().flatten()
    return Net()
