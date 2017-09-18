import math

import torch
import torch.nn as nn
import torch.nn.functional as F


def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1 or classname.find('Linear') != -1:
        nn.init.orthogonal(m.weight.data)
        if m.bias is not None:
            m.bias.data.fill_(0)


# Necessary for my KFAC implementation.
class AddBias(nn.Module):
    def __init__(self, out_features):
        super(AddBias, self).__init__()
        self.bias = nn.Parameter(torch.zeros(out_features, 1))

    def forward(self, x):
        if x.dim() == 2:
            bias = self.bias.t().view(1, -1)
        else:
            bias = self.bias.t().view(1, -1, 1, 1)

        return x + bias


class ActorCritic(torch.nn.Module):
    def __init__(self, num_inputs, action_space):
        super(ActorCritic, self).__init__()
        self.conv1 = nn.Conv2d(num_inputs, 32, 8, stride=4, bias=False)
        self.ab1 = AddBias(32)
        self.conv2 = nn.Conv2d(32, 64, 4, stride=2, bias=False)
        self.ab2 = AddBias(64)
        self.conv3 = nn.Conv2d(64, 32, 3, stride=1, bias=False)
        self.ab3 = AddBias(32)

        self.linear1 = nn.Linear(32 * 7 * 7, 512, bias=False)
        self.ab_fc1 = AddBias(512)

        num_outputs = action_space.n
        self.critic_linear = nn.Linear(512, 1, bias=False)
        self.ab_fc2 = AddBias(1)

        self.actor_linear = nn.Linear(512, num_outputs, bias=False)
        self.ab_fc3 = AddBias(num_outputs)

        self.apply(weights_init)

        self.conv1.weight.data.mul_(math.sqrt(2))  # Multiplier for relu
        self.conv2.weight.data.mul_(math.sqrt(2))  # Multiplier for relu
        self.conv3.weight.data.mul_(math.sqrt(2))  # Multiplier for relu
        self.linear1.weight.data.mul_(math.sqrt(2))  # Multiplier for relu

        self.train()

    def forward(self, inputs):
        x = self.conv1(inputs / 255.0)
        x = self.ab1(x)
        x = F.relu(x)

        x = self.conv2(x)
        x = self.ab2(x)
        x = F.relu(x)

        x = self.conv3(x)
        x = self.ab3(x)
        x = F.relu(x)

        x = x.view(-1, 32 * 7 * 7)
        x = self.linear1(x)
        x = self.ab_fc1(x)
        x = F.relu(x)

        return self.ab_fc2(self.critic_linear(x)), self.ab_fc3(
            self.actor_linear(x))


class GaussianActorCritic(nn.Module):

    def __init__(self, num_inputs, num_outputs, hidden=64):
        super(GaussianActorCritic, self).__init__()
        self.fc1 = nn.Linear(num_inputs, hidden)
        self.ab_fc1 = AddBias(hidden)
        self.fc2 = nn.Linear(hidden, hidden)
        self.ab_fc2 = AddBias(hidden)

        self.action_mean = nn.Linear(hidden, num_outputs)
        self.ab_action_mean = AddBias(num_outputs)
        self.action_mean.weight.data.mul_(0.1)
        self.action_mean.bias.data.mul_(0.0)
        self.action_log_std = nn.Linear(hidden, num_outputs)
        self.ab_action_log_std = AddBias(num_outputs)

        self.value_head = nn.Linear(hidden, 1)
        self.ab_value = AddBias(1)

        self.apply(weights_init)

    def forward(self, x, old=False):
        x = F.tanh(self.fc1(x))
        x = self.ab_fc1(x)
        x = F.tanh(self.fc2(x))
        x = self.ab_fc2(x)

        action_mean = self.action_mean(x)
        action_mean = self.ab_action_mean(action_mean)

        action_log_std = self.action_log_std(x)
        action_log_std = self.ab_action_log_std(action_log_std)
        action_std = torch.exp(action_log_std)

        value = self.value_head(x)
        value = self.ab_value(value)

        return action_mean, action_log_std, action_std, value
