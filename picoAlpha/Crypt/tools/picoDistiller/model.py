"""Reduced TinyGyal-compatible convolutional topology.
Input and policy indices match picoAlpha/src/net.cpp.
Architectural differences: channels 16->8, residual blocks 2->1;
SE and both policy/value heads keep their original structures.
"""
import torch
from torch import nn

POLICY_PLANES=73
POLICY_SIZE=POLICY_PLANES*64

class SEBlock(nn.Module):
    def __init__(self,channels):
        super().__init__()
        self.fc1=nn.Linear(channels,channels)
        self.fc2=nn.Linear(channels,channels*2)
    def forward(self,x):
        pooled=x.mean(dim=(2,3))
        a,b=self.fc2(torch.relu(self.fc1(pooled))).chunk(2,dim=1)
        return x*torch.sigmoid(a)[:,:,None,None]+b[:,:,None,None]

class ResidualBlock(nn.Module):
    def __init__(self,channels):
        super().__init__()
        self.conv1=nn.Conv2d(channels,channels,3,padding=1,bias=False)
        self.bn1=nn.BatchNorm2d(channels)
        self.conv2=nn.Conv2d(channels,channels,3,padding=1,bias=False)
        self.bn2=nn.BatchNorm2d(channels)
        self.se=SEBlock(channels)
    def forward(self,x):
        residual=self.bn2(self.conv2(torch.relu(self.bn1(self.conv1(x)))))
        return torch.relu(x+self.se(residual))

class AlphaZeroMicroNet(nn.Module):
    def __init__(self,input_channels=112,filters=8):
        super().__init__()
        if input_channels!=112 or filters!=8:
            raise ValueError('This training profile requires 112 planes and 8 filters')
        self.conv_init=nn.Conv2d(112,8,3,padding=1,bias=False)
        self.bn_init=nn.BatchNorm2d(8)
        self.res_block=ResidualBlock(8)
        self.policy_conv1=nn.Conv2d(8,8,3,padding=1,bias=False)
        self.policy_bn1=nn.BatchNorm2d(8)
        self.policy_conv2=nn.Conv2d(8,80,3,padding=1,bias=True)
        self.value_conv=nn.Conv2d(8,32,1,bias=False)
        self.value_bn=nn.BatchNorm2d(32)
        self.value_fc1=nn.Linear(32*64,128)
        self.value_fc2=nn.Linear(128,1)
    def forward(self,x):
        x=self.res_block(torch.relu(self.bn_init(self.conv_init(x))))
        p=self.policy_conv2(torch.relu(self.policy_bn1(self.policy_conv1(x))))
        # Native firmware indexes first 73 of 80 policy channels, 64 squares each.
        p=p[:,:POLICY_PLANES].flatten(1)
        v=torch.relu(self.value_bn(self.value_conv(x))).flatten(1)
        v=torch.relu(self.value_fc1(v))
        return p,torch.tanh(self.value_fc2(v))
