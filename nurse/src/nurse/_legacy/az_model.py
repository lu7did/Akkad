#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* az_model.py
#* Independent dual-head AlphaZero network. Requires PyTorch for AZ only.
#* v0.6.153
#=================================================================================================================*
"""Independent dual-head AlphaZero network. Requires PyTorch for AZ only."""
from __future__ import annotations
from .evaluators.npz import INPUT_SIZE
from .az_core import ACTION_SIZE

ARCHITECTURE='sargon-az-782-128-64-p4672-v1'


def build_model(torch):
    class PolicyValueNet(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.fc1=torch.nn.Linear(INPUT_SIZE+1,128)
            self.fc2=torch.nn.Linear(128,64)
            self.policy=torch.nn.Linear(64,ACTION_SIZE)
            self.value=torch.nn.Linear(64,1)
        def forward(self, x, halfmove):
            x=torch.cat((x, (halfmove/100.0).reshape(-1,1)),dim=1)
            h=torch.relu(self.fc2(torch.relu(self.fc1(x))))
            return self.policy(h), torch.tanh(self.value(h).squeeze(-1))
    return PolicyValueNet()
